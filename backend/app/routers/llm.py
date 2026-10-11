import logging

import openai
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Message, Paper
from app.services import llm

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/papers")


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def _paper_or_404(db: Session, paper_id: int) -> Paper:
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


def _llm_http_error(e: Exception) -> HTTPException:
    if isinstance(e, llm.LLMNotConfigured):
        return HTTPException(status_code=503, detail=str(e))
    # Never echo OpenAI's raw message to the browser: it can contain part of the API key.
    log.warning("LLM call failed: %s", type(e).__name__)
    if isinstance(e, openai.AuthenticationError):
        detail = "OpenAI rejected the API key. Check OPENAI_API_KEY in backend/.env and restart the backend."
    elif isinstance(e, openai.RateLimitError):
        detail = "OpenAI rate limit or quota exceeded. Check your OpenAI billing and usage."
    elif isinstance(e, openai.APIConnectionError):
        detail = "Could not reach OpenAI. Check your internet connection."
    else:
        detail = f"LLM request failed ({type(e).__name__})."
    return HTTPException(status_code=502, detail=detail)


@router.post("/{paper_id}/summary")
async def summary(paper_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    paper = _paper_or_404(db, paper_id)
    if paper.summary and not refresh:
        return {"summary": paper.summary, "cached": True}
    try:
        text = await llm.summarize(paper)
    except (llm.LLMNotConfigured, openai.OpenAIError) as e:
        raise _llm_http_error(e)
    paper.summary = text
    db.commit()
    return {"summary": text, "cached": False}


@router.post("/{paper_id}/ask")
async def ask(paper_id: int, body: AskIn, db: Session = Depends(get_db)):
    paper = _paper_or_404(db, paper_id)
    history = [{"role": m.role, "content": m.content} for m in paper.messages]
    question = body.question.strip()
    try:
        text = await llm.answer(paper, history, question)
    except (llm.LLMNotConfigured, openai.OpenAIError) as e:
        raise _llm_http_error(e)
    db.add(Message(paper_id=paper.id, role="user", content=question))
    db.add(Message(paper_id=paper.id, role="assistant", content=text))
    db.commit()
    return {"answer": text}
