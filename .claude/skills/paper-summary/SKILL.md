---
name: paper-summary
description: Work on LLM paper summaries. Use when changing the summary prompt, model, caching or context limits.
---

# Paper summary

- Code: `summarize` and `paper_context` in `backend/app/services/llm.py`; route `POST /api/papers/{id}/summary` (add `?refresh=1` to regenerate) in `backend/app/routers/llm.py`.
- Context: `paper_context` builds title, authors, year and the full text, truncated to 300,000 characters. Papers with no full text fall back to the abstract and the prompt says so.
- The summary is cached in `papers.summary`; repeat calls return `{summary, cached: true}` without an LLM call.
- Provider: OpenAI chat completions via the `openai` SDK, model from `OPENAI_MODEL` (default `gpt-4o-mini`), key from `OPENAI_API_KEY` (loaded by `config.py`). Never hard-code or commit keys. Missing key returns a clear 503; upstream errors return 502.
- Summaries must come from the paper's content, not only metadata (homework requirement).
- Frontend: `SummaryPanel.jsx` (generate/regenerate, loading and error states).
