"""Round 1: services/llm.py (client setup, prompt construction, history window)."""
from types import SimpleNamespace

import pytest

from app.config import settings
from app.models import Paper
from app.services import llm

pytestmark = pytest.mark.anyio


class FakeCompletions:
    def __init__(self, content="  answer  "):
        self.content = content
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


@pytest.fixture
def fake_openai(monkeypatch):
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    return completions


def paper(**kw):
    base = dict(title="T", authors=["A B"], year=2020, abstract="Abs", full_text=None)
    return Paper(**{**base, **kw})


@pytest.mark.parametrize("key", ["", "your-key-here"])
def test_get_client_requires_key(monkeypatch, key):
    monkeypatch.setattr(settings, "openai_api_key", key)
    monkeypatch.setattr(llm, "_client", None)
    with pytest.raises(llm.LLMNotConfigured):
        llm._get_client()


def test_get_client_is_cached(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(llm, "_client", None)
    assert llm._get_client() is llm._get_client()


def test_context_uses_full_text_and_truncates(monkeypatch):
    monkeypatch.setattr(llm, "MAX_CONTEXT_CHARS", 10)
    ctx = llm.paper_context(paper(full_text="0123456789ABCDEF"))
    assert "Full text of the paper:\n0123456789" in ctx
    assert "ABCDEF" not in ctx
    assert "Abs" not in ctx


def test_context_falls_back_to_abstract():
    ctx = llm.paper_context(paper(authors=[], year=None))
    assert "Authors: unknown" in ctx and "Year: unknown" in ctx
    assert "only the abstract is" in ctx and "Abstract:\nAbs" in ctx


def test_context_without_abstract():
    assert "(no abstract available)" in llm.paper_context(paper(abstract=None))


async def test_summarize_sends_prompt_and_strips(fake_openai, monkeypatch):
    monkeypatch.setattr(settings, "openai_model", "gpt-test")
    assert await llm.summarize(paper()) == "answer"
    call = fake_openai.calls[0]
    assert call["model"] == "gpt-test"
    assert call["messages"][0] == {"role": "system", "content": llm.SUMMARY_PROMPT}
    assert call["messages"][1]["role"] == "user" and "Title: T" in call["messages"][1]["content"]


async def test_answer_keeps_last_20_history_messages(fake_openai):
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(30)]
    await llm.answer(paper(), history, "Q?")
    msgs = fake_openai.calls[0]["messages"]
    assert msgs[0]["role"] == "system" and msgs[0]["content"].startswith(llm.QA_PROMPT)
    assert [m["content"] for m in msgs[1:-1]] == [f"m{i}" for i in range(10, 30)]
    assert msgs[-1] == {"role": "user", "content": "Q?"}


async def test_empty_completion_becomes_empty_string(fake_openai):
    fake_openai.content = None
    assert await llm.summarize(paper()) == ""
