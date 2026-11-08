"""Round 1: routers/llm.py error mapping (status codes, no leaked OpenAI messages)."""
import httpx2
import openai
import pytest

from app.models import Paper
from app.services import llm

REQ = httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")
SECRET = "sk-proj-SECRET123"


def status_error(cls, code):
    return cls(f"Incorrect API key provided: {SECRET}", response=httpx2.Response(code, request=REQ), body=None)


@pytest.fixture
def paper_id(session_factory):
    with session_factory() as db:
        p = Paper(source="upload", title="T", authors=[], full_text="text")
        db.add(p)
        db.commit()
        return p.id


@pytest.mark.parametrize(
    "error, status, fragment",
    [
        (lambda: llm.LLMNotConfigured("OPENAI_API_KEY is not set"), 503, "OPENAI_API_KEY is not set"),
        (lambda: status_error(openai.AuthenticationError, 401), 502, "rejected the API key"),
        (lambda: status_error(openai.RateLimitError, 429), 502, "rate limit"),
        (lambda: openai.APIConnectionError(request=REQ), 502, "Could not reach OpenAI"),
        (lambda: status_error(openai.InternalServerError, 500), 502, "LLM request failed (InternalServerError)"),
    ],
)
@pytest.mark.parametrize("endpoint", ["summary", "ask"])
def test_llm_errors_are_mapped(client, paper_id, monkeypatch, error, status, fragment, endpoint):
    async def boom(*_a, **_k):
        raise error()

    monkeypatch.setattr(llm, "summarize", boom)
    monkeypatch.setattr(llm, "answer", boom)
    r = client.post(f"/api/papers/{paper_id}/{endpoint}", json={"question": "q"})
    assert r.status_code == status
    assert fragment in r.json()["detail"]
    assert SECRET not in r.text
    # nothing is persisted when the LLM call fails
    detail = client.get(f"/api/papers/{paper_id}").json()
    assert detail["summary"] is None and detail["messages"] == []
