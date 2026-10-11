---
name: paper-search
description: Work on paper search (OpenAlex) in the research assistant backend. Use when changing search results, the search API, or switching search providers.
---

# Paper search

- Code: `backend/app/services/openalex.py`; route `GET /api/search?q=&limit=` in `backend/app/routers/search.py`.
- Provider: OpenAlex (`https://api.openalex.org/works`), free, no key. Send an email via `mailto=` for the polite pool. Use `httpx.AsyncClient` with a timeout.
- OpenAlex returns abstracts as an inverted index (word -> positions); `abstract_from_index` rebuilds the text.
- Result shape (camelCase in JSON): `{externalId, source: 'openalex', title, authors[], year, abstract, url, pdfUrl}`. `pdfUrl` is null unless the paper is open access.
- Limit is capped at 25 in the route. Missing or empty `q` returns 400. Upstream failure returns 502.
- To switch providers (arXiv, Semantic Scholar), keep this result shape so the frontend and the save route do not change. Semantic Scholar often returns 429 without a key.
- Frontend: `SearchPage.jsx`, `PaperCard.jsx`, calls via `frontend/src/api.js`.
