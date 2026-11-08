"""Round 2: tests derived from the README requirements, plus stronger versions of
weak Round 0 assertions. Each test names the requirement it checks."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app import db as app_db
from app.config import settings
from app.main import app
from app.models import Message, Paper
from app.routers import papers as papers_router
from app.services import llm

from .conftest import BODY, make_pdf

OPENALEX = "https://api.openalex.org/works"


@pytest.fixture(autouse=True)
def no_pdf_download(monkeypatch):
    async def none(*_a, **_k):
        return None

    async def no_urls(*_a, **_k):
        return []

    monkeypatch.setattr(papers_router, "download_pdf_text", none)
    monkeypatch.setattr(papers_router, "fallback_pdf_urls", no_urls)


def save(client, **kw):
    r = client.post("/api/papers", json={"title": "Paper", **kw})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


# ---------- Search ----------


@pytest.mark.parametrize("limit, sent", [(1, "1"), (25, "25"), (26, "25")])
def test_search_limit_boundaries(client, no_network, limit, sent):
    route = no_network.get(OPENALEX).respond(json={"results": []})
    assert client.get("/api/search", params={"q": "x", "limit": limit}).status_code == 200
    assert route.calls.last.request.url.params["per-page"] == sent


def test_search_default_limit_and_query_trimmed(client, no_network):
    route = no_network.get(OPENALEX).respond(json={"results": []})
    client.get("/api/search", params={"q": "  graph nets  "})
    params = route.calls.last.request.url.params
    assert params["search"] == "graph nets" and params["per-page"] == "10"
    assert "mailto" not in params


@pytest.mark.parametrize("limit", [0, -1])
def test_search_rejects_non_positive_limit(client, limit):
    assert client.get("/api/search", params={"q": "x", "limit": limit}).status_code == 422


def test_search_sends_polite_pool_email(client, no_network, monkeypatch):
    monkeypatch.setattr(settings, "openalex_mailto", "me@example.org")
    route = no_network.get(OPENALEX).respond(json={"results": []})
    client.get("/api/search", params={"q": "x"})
    assert route.calls.last.request.url.params["mailto"] == "me@example.org"


def test_search_result_fallbacks(client, no_network):
    no_network.get(OPENALEX).respond(
        json={
            "results": [
                {
                    "id": "https://openalex.org/W2",
                    "title": None,
                    "display_name": "Display Name Title",
                    "authorships": [{"author": {"display_name": None}}, {"author": {"display_name": "Kim Lee"}}],
                    "primary_location": {"landing_page_url": "https://pub.org/w2"},
                    "best_oa_location": None,
                },
                {"id": "https://openalex.org/W3"},
            ]
        }
    )
    first, second = client.get("/api/search", params={"q": "x"}).json()
    assert first["title"] == "Display Name Title"
    assert first["authors"] == ["Kim Lee"]
    assert first["url"] == "https://pub.org/w2"
    assert first["pdfUrl"] is None and first["abstract"] is None
    assert second["title"] == "(untitled)"
    assert second["url"] == "https://openalex.org/W3"
    assert second["authors"] == [] and second["year"] is None


# ---------- Library ----------


def test_library_lists_newest_first(client):
    ids = [save(client, externalId=f"W{i}", title=f"P{i}") for i in range(3)]
    assert [p["id"] for p in client.get("/api/papers").json()] == ids[::-1]


def test_saved_papers_survive_restart(session_factory, client):
    pid = save(client, title="Persistent")
    client.close()
    # a brand-new client on the same database file still sees the paper
    new = TestClient(app)
    assert new.get(f"/api/papers/{pid}").json()["title"] == "Persistent"


def test_delete_also_deletes_chat_history(client, session_factory, monkeypatch):
    async def fake_answer(*_a):
        return "a"

    monkeypatch.setattr(llm, "answer", fake_answer)
    pid = save(client)
    other = save(client, externalId="W-other")
    client.post(f"/api/papers/{pid}/ask", json={"question": "q"})
    client.post(f"/api/papers/{other}/ask", json={"question": "q"})
    client.delete(f"/api/papers/{pid}")
    with session_factory() as db:
        assert db.scalar(select(func.count()).where(Message.paper_id == pid)) == 0
        assert db.scalar(select(func.count()).where(Message.paper_id == other)) == 2


def test_full_text_is_not_exposed_in_api(client, monkeypatch):
    async def text(_url):
        return "SECRET FULL TEXT"

    monkeypatch.setattr(papers_router, "download_pdf_text", text)
    pid = save(client, pdfUrl="https://example.org/p.pdf")
    assert "SECRET FULL TEXT" not in client.get(f"/api/papers/{pid}").text
    assert "SECRET FULL TEXT" not in client.get("/api/papers").text


def test_edit_all_metadata_fields_persists(client):
    pid = save(client, authors=["Old"], year=1999, abstract="old")
    patch = {"title": "New", "authors": ["X Y", "Z W"], "year": 2024, "abstract": "new"}
    assert client.patch(f"/api/papers/{pid}", json=patch).status_code == 200
    got = client.get(f"/api/papers/{pid}").json()
    assert {k: got[k] for k in patch} == patch


def test_patch_missing_paper_404(client):
    assert client.patch("/api/papers/999", json={"title": "x"}).status_code == 404


# ---------- Upload ----------


def upload(client, data, name="paper.pdf"):
    return client.post("/api/papers/upload", files={"file": (name, data, "application/pdf")})


def test_upload_extracts_all_metadata(client, no_network, sample_pdf):
    no_network.post("http://grobid.test/api/processHeaderDocument").respond(status_code=503)
    body = upload(client, sample_pdf).json()
    assert body["authors"] == ["Alice Smith", "Bob Jones"]
    assert body["year"] == 2021
    assert body["abstract"].startswith("We propose a method")
    assert body["externalId"] is None and body["url"] is None


def test_upload_uses_filename_when_no_title_found(client, no_network):
    no_network.post("http://grobid.test/api/processHeaderDocument").respond(status_code=503)
    pdf = make_pdf([(w, 10) for w in BODY.split()[:60]])  # one word per line: no title candidate
    r = upload(client, pdf, name="my.great.paper.pdf")
    assert r.status_code == 201
    assert r.json()["title"] == "my.great.paper"


def test_upload_size_limit(client, monkeypatch, sample_pdf):
    monkeypatch.setattr(papers_router, "MAX_PDF_BYTES", len(sample_pdf) - 1)
    r = upload(client, sample_pdf)
    assert r.status_code == 413
    assert client.get("/api/papers").json() == []


def test_rejected_uploads_are_not_saved(client):
    upload(client, b"not a pdf")
    upload(client, make_pdf([("tiny", 10)]))  # scanned/no text layer
    assert client.get("/api/papers").json() == []


# ---------- Summary and Q&A ----------


def test_refresh_regenerates_and_replaces_summary(client, monkeypatch):
    versions = iter(["v1", "v2"])

    async def fake(_paper):
        return next(versions)

    monkeypatch.setattr(llm, "summarize", fake)
    pid = save(client)
    client.post(f"/api/papers/{pid}/summary")
    assert client.post(f"/api/papers/{pid}/summary?refresh=1").json() == {"summary": "v2", "cached": False}
    detail = client.get(f"/api/papers/{pid}").json()
    assert detail["summary"] == "v2" and detail["hasSummary"] is True


def test_follow_up_questions_receive_earlier_turns(client, monkeypatch):
    seen = []

    async def fake(paper, history, question):
        seen.append((list(history), question))
        return f"A:{question}"

    monkeypatch.setattr(llm, "answer", fake)
    pid = save(client)
    client.post(f"/api/papers/{pid}/ask", json={"question": "  first  "})
    client.post(f"/api/papers/{pid}/ask", json={"question": "second"})
    assert seen[0] == ([], "first")
    assert seen[1] == (
        [{"role": "user", "content": "first"}, {"role": "assistant", "content": "A:first"}],
        "second",
    )
    msgs = client.get(f"/api/papers/{pid}").json()["messages"]
    assert [m["content"] for m in msgs] == ["first", "A:first", "second", "A:second"]


def test_chat_history_is_per_paper(client, monkeypatch):
    async def fake(paper, history, question):
        assert history == []
        return "a"

    monkeypatch.setattr(llm, "answer", fake)
    a, b = save(client, externalId="A"), save(client, externalId="B")
    client.post(f"/api/papers/{a}/ask", json={"question": "q"})
    client.post(f"/api/papers/{b}/ask", json={"question": "q"})


def test_question_length_limit(client):
    pid = save(client)
    assert client.post(f"/api/papers/{pid}/ask", json={"question": "x" * 2001}).status_code == 422


def test_summary_missing_paper_404(client):
    assert client.post("/api/papers/999/summary").status_code == 404


def test_answers_grounded_in_selected_paper_text(client, session_factory, monkeypatch):
    """The LLM receives the selected paper's full text (or its abstract if none)."""
    captured = []

    async def fake_complete(messages):
        captured.append(messages)
        return "ok"

    monkeypatch.setattr(llm, "_complete", fake_complete)
    with session_factory() as db:
        full = Paper(source="upload", title="Full", authors=[], full_text="UNIQUE_BODY_TEXT", abstract="ABS1")
        bare = Paper(source="openalex", title="Bare", authors=[], abstract="ONLY_ABSTRACT")
        db.add_all([full, bare])
        db.commit()
        full_id, bare_id = full.id, bare.id
    client.post(f"/api/papers/{full_id}/ask", json={"question": "q"})
    client.post(f"/api/papers/{bare_id}/summary")
    assert "UNIQUE_BODY_TEXT" in captured[0][0]["content"] and "ONLY_ABSTRACT" not in captured[0][0]["content"]
    assert "ONLY_ABSTRACT" in captured[1][1]["content"] and "full text is not available" in captured[1][1]["content"]


# ---------- App startup with the real database wiring ----------


def test_startup_creates_tables_and_real_get_db_works(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'lib.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(app_db, "engine", engine)
    monkeypatch.setattr(app_db, "SessionLocal", sessionmaker(bind=engine, autoflush=False))
    with TestClient(app) as c:  # runs the lifespan -> init_db()
        assert c.get("/api/papers").json() == []
        assert c.post("/api/papers", json={"title": "x"}).status_code == 201
    engine.dispose()


def test_foreign_keys_enabled_on_real_engine():
    with app_db.engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
