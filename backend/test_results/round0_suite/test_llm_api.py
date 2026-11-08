import pytest

from app.routers import papers as papers_router
from app.services import llm


@pytest.fixture
def paper_id(client, monkeypatch):
    async def none(*_a, **_k):
        return None

    async def no_urls(*_a, **_k):
        return []

    monkeypatch.setattr(papers_router, "download_pdf_text", none)
    monkeypatch.setattr(papers_router, "fallback_pdf_urls", no_urls)
    return client.post("/api/papers", json={"title": "T", "abstract": "Abs"}).json()["id"]


def test_summary_generated_and_cached(client, paper_id, monkeypatch):
    calls = []

    async def fake_summarize(paper):
        calls.append(paper.id)
        return "A summary"

    monkeypatch.setattr(llm, "summarize", fake_summarize)
    r1 = client.post(f"/api/papers/{paper_id}/summary").json()
    r2 = client.post(f"/api/papers/{paper_id}/summary").json()
    assert r1 == {"summary": "A summary", "cached": False}
    assert r2 == {"summary": "A summary", "cached": True}
    assert len(calls) == 1


def test_summary_refresh(client, paper_id, monkeypatch):
    async def fake_summarize(paper):
        return "A summary"

    monkeypatch.setattr(llm, "summarize", fake_summarize)
    client.post(f"/api/papers/{paper_id}/summary")
    r = client.post(f"/api/papers/{paper_id}/summary", params={"refresh": 1})
    assert r.json()["cached"] is False


def test_summary_without_key_is_503(client, paper_id):
    r = client.post(f"/api/papers/{paper_id}/summary")
    assert r.status_code == 503


def test_ask_stores_history(client, paper_id, monkeypatch):
    async def fake_answer(paper, history, question):
        return f"answer to {question}"

    monkeypatch.setattr(llm, "answer", fake_answer)
    r = client.post(f"/api/papers/{paper_id}/ask", json={"question": "What?"})
    assert r.status_code == 200
    assert r.json() == {"answer": "answer to What?"}
    msgs = client.get(f"/api/papers/{paper_id}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]


def test_ask_empty_question_422(client, paper_id):
    r = client.post(f"/api/papers/{paper_id}/ask", json={"question": ""})
    assert r.status_code == 422


def test_ask_missing_paper_404(client):
    r = client.post("/api/papers/999/ask", json={"question": "hi"})
    assert r.status_code == 404
