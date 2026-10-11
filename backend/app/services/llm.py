import logging

from openai import AsyncOpenAI

from app.config import settings
from app.models import Paper

log = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 300_000
MAX_HISTORY_MESSAGES = 20


class LLMNotConfigured(Exception):
    pass


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    key = settings.openai_api_key
    if not key or key == "your-key-here":
        raise LLMNotConfigured("OPENAI_API_KEY is not set in backend/.env")
    if _client is None:
        _client = AsyncOpenAI(api_key=key)
    return _client


async def _complete(messages: list[dict]) -> str:
    resp = await _get_client().chat.completions.create(
        model=settings.openai_model, messages=messages, temperature=0.2
    )
    return (resp.choices[0].message.content or "").strip()


def paper_context(paper: Paper) -> str:
    header = (
        f"Title: {paper.title}\n"
        f"Authors: {', '.join(paper.authors) or 'unknown'}\n"
        f"Year: {paper.year or 'unknown'}\n"
    )
    if paper.full_text:
        body = paper.full_text[:MAX_CONTEXT_CHARS]
        return f"{header}\nFull text of the paper:\n{body}"
    return (
        f"{header}\nNOTE: the full text is not available; only the abstract is.\n"
        f"Abstract:\n{paper.abstract or '(no abstract available)'}"
    )


SUMMARY_PROMPT = (
    "You are a research assistant. Summarize the paper below for a fellow researcher. "
    "Base the summary on the paper's content, not just its title. Use these sections: "
    "Problem, Approach, Key Results, Limitations. Be concise (about 200-300 words). "
    "If only the abstract is available, say so at the start and summarize what it supports."
)

QA_PROMPT = (
    "You answer questions about one research paper, provided below. Answer only from the "
    "paper. If the answer is not in the paper, say that the paper does not say. "
    "Be concise and specific; mention sections, datasets or numbers when the paper gives them.\n\n"
)


async def summarize(paper: Paper) -> str:
    return await _complete(
        [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": paper_context(paper)},
        ]
    )


async def answer(paper: Paper, history: list[dict], question: str) -> str:
    messages = [
        {"role": "system", "content": QA_PROMPT + paper_context(paper)},
        *history[-MAX_HISTORY_MESSAGES:],
        {"role": "user", "content": question},
    ]
    return await _complete(messages)
