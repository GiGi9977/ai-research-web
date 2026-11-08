"""Round 2: faults found by requirement-based tests.

Each test describes the *intended* behaviour and is marked xfail(strict=True) because
the current application violates it. When a bug is fixed, the test starts passing,
strict xfail turns that into a failure, and the marker should be removed.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import papers as papers_router
from app.services import llm
from app.services.pdf import download_pdf_text

from .conftest import make_pdf


@pytest.fixture(autouse=True)
def no_pdf_download(monkeypatch):
    async def none(*_a, **_k):
        return None

    async def no_urls(*_a, **_k):
        return []

    monkeypatch.setattr(papers_router, "download_pdf_text", none)
    monkeypatch.setattr(papers_router, "fallback_pdf_urls", no_urls)


@pytest.fixture
def lenient(client):
    # Report unhandled server errors as HTTP 500 instead of raising in the test.
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.xfail(strict=True, reason="BUG-1: PATCH authors=null stores NULL; paper and whole library then 500")
def test_bug1_patch_authors_null_does_not_break_library(lenient):
    pid = lenient.post("/api/papers", json={"title": "T", "authors": ["A B"]}).json()["id"]
    r = lenient.patch(f"/api/papers/{pid}", json={"authors": None})
    assert r.status_code in (200, 422)
    assert lenient.get(f"/api/papers/{pid}").status_code == 200
    assert lenient.get("/api/papers").status_code == 200


@pytest.mark.xfail(strict=True, reason="BUG-2: whitespace-only question passes validation and is sent to the LLM")
def test_bug2_blank_question_rejected(client, monkeypatch):
    calls = []

    async def fake(paper, history, question):
        calls.append(question)
        return "a"

    monkeypatch.setattr(llm, "answer", fake)
    pid = client.post("/api/papers", json={"title": "T"}).json()["id"]
    r = client.post(f"/api/papers/{pid}/ask", json={"question": "   \n "})
    assert r.status_code == 422
    assert calls == []


@pytest.mark.xfail(strict=True, reason="BUG-3: whitespace-only title accepted when saving")
def test_bug3_blank_title_rejected_on_save(client):
    assert client.post("/api/papers", json={"title": "   "}).status_code == 422


@pytest.mark.xfail(strict=True, reason="BUG-3: whitespace-only title accepted when editing")
def test_bug3_blank_title_rejected_on_edit(client):
    pid = client.post("/api/papers", json={"title": "T"}).json()["id"]
    assert client.patch(f"/api/papers/{pid}", json={"title": "  "}).status_code == 422


@pytest.mark.anyio
@pytest.mark.xfail(strict=True, reason="BUG-4: SSRF guard checks only the first URL; redirects to private hosts are followed")
async def test_bug4_redirect_to_private_host_is_blocked(fake_dns, no_network, sample_pdf):
    no_network.get("https://example.org/p.pdf").respond(
        status_code=302, headers={"Location": "http://localhost/internal.pdf"}
    )
    internal = no_network.get("http://localhost/internal.pdf").respond(content=sample_pdf)
    assert await download_pdf_text("https://example.org/p.pdf") is None
    assert not internal.called


@pytest.fixture
def anyio_backend():
    return "asyncio"
