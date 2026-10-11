# AI Research Assistant — Architecture Plan

Stack: **FastAPI** (Python) backend, **React + Vite** frontend, **SQLite** local DB, **OpenAlex** for paper search, **OpenAI** for the LLM.

## 1. Requirements → components

| HW requirement | Backend | Frontend |
|---|---|---|
| Search papers (title, authors, year, abstract, link) | `GET /api/search` → OpenAlex | `SearchPage`, `PaperCard` |
| Save to local library (persists across restart/refresh) | `POST/GET/DELETE /api/papers` → SQLite | `LibraryPage` |
| Upload PDF, extract title/authors/year/abstract | `POST /api/papers/upload` → PyMuPDF text + GROBID metadata (no LLM) | `UploadDropzone` |
| LLM summary from paper content | `POST /api/papers/{id}/summary` | `PaperDetail` summary tab |
| Q&A about a paper | `POST /api/papers/{id}/ask` | `PaperDetail` chat tab |

## 2. System diagram

```
React (Vite, :5173) ──/api proxy──▶ FastAPI (:3001)
                                      ├─ routers/ (search, papers, upload, llm)
                                      ├─ services/
                                      │    ├─ openalex.py   ──▶ api.openalex.org
                                      │    ├─ pdf.py        (PyMuPDF text extraction)
                                      │    ├─ metadata.py   ──▶ GROBID :8070 (processHeaderDocument, TEI XML) → PyMuPDF heuristic fallback
                                      │    └─ llm.py        ──▶ OpenAI chat completions
                                      └─ db.py ──▶ data/library.db (SQLite)
```

## 3. Backend layout (`backend/`)

```
backend/
  app/
    main.py            # FastAPI app, CORS, router registration, lifespan (init DB)
    config.py          # pydantic-settings: OPENAI_API_KEY, OPENAI_MODEL, GROBID_URL, PORT
    db.py              # SQLAlchemy engine/session, create_all on startup
    models.py          # ORM: Paper, Message
    schemas.py         # Pydantic request/response models (camelCase aliases)
    routers/
      search.py        # GET /api/search
      papers.py        # library CRUD + upload
      llm.py           # summary + ask
    services/
      openalex.py      # query, rebuild abstract from inverted index
      pdf.py           # extract text, reject <200 chars (scanned) with 422
      metadata.py      # GROBID header parse (TEI XML) → PyMuPDF heuristic fallback; no LLM
      llm.py           # paper_context(), summarize(), answer()
  requirements.txt     # fastapi, uvicorn, sqlalchemy, httpx, pymupdf, python-multipart, openai, pydantic-settings, python-dotenv
  .env / .env.example  # already present (change PORT/keys only here; never commit .env)
```

### Data model
- `papers`: `id`, `external_id` (unique, nullable for uploads), `source` (`openalex`|`upload`), `title`, `authors` (JSON), `year`, `abstract`, `url`, `pdf_url`, `full_text`, `summary`, `created_at`
- `messages`: `id`, `paper_id` (FK, ON DELETE CASCADE), `role` (`user`|`assistant`), `content`, `created_at`

### API
| Method | Path | Notes |
|---|---|---|
| GET | `/api/search?q=&limit=` | limit capped at 25; missing `q` → 400. Returns `{externalId, source, title, authors[], year, abstract, url, pdfUrl}` |
| GET | `/api/papers` | list library (no full_text in payload) |
| GET | `/api/papers/{id}` | paper + chat messages |
| POST | `/api/papers` | save search result; dedupe on `external_id`; if `pdfUrl`, download and extract full text (failure logged, not fatal) |
| POST | `/api/papers/upload` | multipart `file`, 30 MB cap, `source='upload'` |
| PATCH | `/api/papers/{id}` | edit title/authors/year/abstract (fixes extraction errors) |
| DELETE | `/api/papers/{id}` | cascades messages |
| POST | `/api/papers/{id}/summary?refresh=1` | cached in `papers.summary`; returns `{summary, cached}` |
| POST | `/api/papers/{id}/ask` | body `{question}`; returns `{answer}`; stores both turns only on success |
| GET | `/api/health` | liveness |

### Key design decisions
1. **Summaries/Q&A use full text** (HW requires content, not metadata). `paper_context` = title + authors + year + full text truncated to ~300k chars; falls back to abstract and tells the model so.
2. **Q&A grounding**: system prompt contains the paper and says to answer only from it, and to say so if the answer isn't present. Prior messages are loaded from DB and sent before the new question.
3. **Metadata extraction for uploads uses no LLM**: GROBID `processHeaderDocument` (TEI XML parsed for title, authors, year, abstract) is the primary path; if GROBID is down or returns no title, fall back to PyMuPDF layout heuristics (largest-font lines = title, text after "Abstract" heading = abstract, most frequent 19xx/20xx on page 1 = year). Upload works without an API key. Because extraction can be wrong, users can correct fields via `PATCH /api/papers/{id}` and an edit form in `PaperDetail`.
4. **Search provider isolation**: `openalex.py` returns the common result shape, so swapping to arXiv/Semantic Scholar changes nothing else.
5. **Sync vs async**: async routes with `httpx.AsyncClient` for external calls; DB calls are sync SQLAlchemy in threadpool-dispatched `def` routes where simple.
6. **Secrets**: only from env; `.env` git-ignored.
7. **Errors**: consistent `{detail}` via `HTTPException`; 502 for upstream (OpenAlex/OpenAI) failures, 422 for unreadable PDFs.

## 4. Frontend layout (`frontend/`, React + Vite)

```
frontend/src/
  main.jsx, App.jsx          # tab layout: Search | Library
  api.js                     # fetch wrappers for /api/*
  components/
    SearchBar.jsx
    PaperCard.jsx            # title, authors, year, abstract (expand), link, Save/Open buttons
    UploadDropzone.jsx
    PaperDetail.jsx          # metadata + Summary panel + Chat panel
    SummaryPanel.jsx         # generate / regenerate, loading + error states
    ChatPanel.jsx            # message list, input, suggested questions
  pages/
    SearchPage.jsx           # results, "saved" badge, save action
    LibraryPage.jsx          # list, upload, delete, select → PaperDetail
  styles.css
```
- State: React hooks only (`useState`/`useEffect`); no state library needed at this size.
- Vite dev proxy `/api` → `http://localhost:3001` (no CORS pain; CORS still enabled in FastAPI).
- UX details: loading spinners for LLM calls, inline errors, disabled Save for already-saved papers, library loads from the DB on mount (satisfies refresh persistence).

## 5. Build order (milestones)
1. **Scaffold**: FastAPI app + `/api/health`; Vite React app with proxy; README skeleton.
2. **Search**: OpenAlex service + route + `SearchPage`. *Verify with a live query.*
3. **Library**: models, CRUD, save (with PDF full-text download), `LibraryPage`. *Verify persistence across server restart.*
4. **Upload**: PDF text extraction + metadata cascade + `UploadDropzone`. *Verify with a real paper PDF.*
5. **LLM**: summary + Q&A endpoints, `SummaryPanel`/`ChatPanel`. *Verify with 5 sample questions.*
6. **Polish & docs**: error states, README (setup, run, features, structure), `.env.example`, demo script.

## 6. Run
```
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY
uvicorn app.main:app --reload --port 3001

# frontend
cd frontend && npm install && npm run dev

# required for best upload metadata extraction (falls back to heuristics if not running)
docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.1
```

## 7. Housekeeping / open items
- The existing `.claude/skills/*/SKILL.md` files describe a **Node/Express** layout (`backend/src/*.js`, `pdf-parse`). They should be updated to the FastAPI file paths above once implementation starts, or the agent will be steered toward the wrong code.
- `.env.example` already has `PORT=3001`, `GROBID_URL`, `OPENAI_*`; reused as-is.
- `frontend/.vite/` is a stray cache dir and should be git-ignored.
- Deliverables beyond code: README, demo video (search → save → upload → summary → question), reflection report (keep notes/screenshots of agent interactions as you go).
- Out of scope: auth, multi-user, production deployment, tests (HW2).
