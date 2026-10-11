# AI Research Assistant

A small web app for the research workflow: search for papers, save them to a local library, upload PDFs, get an LLM summary of a paper, and ask questions about it.

**Stack:** FastAPI (Python 3.10+) · React + Vite · SQLite · OpenAlex (paper search) · GROBID (PDF metadata) · OpenAI (summaries and Q&A)

## Features

| Feature | How it works |
|---|---|
| **Search** | Keyword search through the OpenAlex API. Results show title, authors, year, abstract and a link. |
| **Save to library** | One click saves a result to SQLite (`backend/data/library.db`). Saved papers survive page refreshes and server restarts. If the paper has an open-access PDF, its full text is downloaded and stored; if that link is broken, the app tries arXiv (by title) and then Unpaywall (optional). |
| **Upload PDF** | Drag and drop a PDF. Text is extracted with PyMuPDF; title, authors, year and abstract come from GROBID, with a PyMuPDF layout heuristic as a fallback. No LLM is involved. |
| **Edit metadata** | Extracted metadata can be wrong, so every paper's title, authors, year and abstract can be edited. |
| **Summary** | An LLM summarizes the paper's full text (Problem, Approach, Key Results, Limitations). Cached, with a Regenerate button. |
| **Ask questions** | Chat about one paper. Answers come only from that paper's text, and follow-up questions use earlier turns. History is stored. |

Papers saved without full text (no PDF found) fall back to the abstract for summaries and Q&A, and the UI says so.

## Project layout

```
backend/
  app/
    main.py               FastAPI app, CORS, startup (creates tables)
    config.py             settings from backend/.env
    db.py, models.py      SQLAlchemy engine and tables (papers, messages)
    schemas.py            Pydantic models (camelCase JSON)
    routers/              search.py, papers.py (library + upload), llm.py (summary, ask)
    services/             openalex.py, pdf.py, pdf_sources.py, metadata.py, llm.py
frontend/
  src/
    App.jsx               Search / Library tabs
    api.js                fetch wrappers for /api/*
    pages/                SearchPage.jsx, LibraryPage.jsx
    components/           PaperCard, PaperDetail, UploadDropzone, SummaryPanel, ChatPanel, RichText
ARCHITECTURE.md           design notes
.claude/skills/           project skills used with the coding agent
```

### API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/search?q=&limit=` | search OpenAlex (limit capped at 25) |
| GET | `/api/papers` | list library |
| GET | `/api/papers/{id}` | paper with summary and chat history |
| POST | `/api/papers` | save a search result |
| POST | `/api/papers/upload` | upload a PDF (multipart field `file`, max 30 MB) |
| PATCH | `/api/papers/{id}` | edit title/authors/year/abstract |
| DELETE | `/api/papers/{id}` | delete paper and its chat |
| POST | `/api/papers/{id}/summary?refresh=1` | generate or fetch the cached summary |
| POST | `/api/papers/{id}/ask` | body `{"question": "..."}` |
| GET | `/api/health` | liveness |

## Setup

You need Python 3.10+, Node 18+, an OpenAI API key, and (recommended) Docker for GROBID.

### 1. Backend
```bash
cd backend
python3.12 -m venv .venv          # any Python 3.10+
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then edit .env and set OPENAI_API_KEY
uvicorn app.main:app --reload --port 3001
```
`.env` is git-ignored. Never commit it. Settings (all optional except the key):

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | required for summaries and Q&A |
| `OPENAI_MODEL` | default `gpt-4o-mini` |
| `GROBID_URL` | default `http://localhost:8070` |
| `OPENALEX_MAILTO` | your email, for OpenAlex's faster "polite pool" |
| `UNPAYWALL_EMAIL` | your email; enables the Unpaywall PDF fallback |

The backend reads `.env` only at startup, so restart it after editing.

### 2. Frontend
```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173, proxies /api to port 3001
```

### 3. GROBID (recommended, for PDF upload metadata)
```bash
docker run -d --name grobid -p 8070:8070 lfoppiano/grobid:0.8.1
```
On Apple Silicon the image runs under emulation and crashes on startup unless Java's container detection is off. Use this instead:
```bash
docker run -d --name grobid --platform linux/amd64 \
  -e JAVA_TOOL_OPTIONS="-XX:-UseContainerSupport" -p 8070:8070 lfoppiano/grobid:0.8.1
```
Wait about 15 seconds; `curl localhost:8070/api/isalive` should print `true`. Without GROBID, uploads use simpler layout heuristics, which are less accurate on authors.

## Using the app
1. **Search** tab: enter a topic, press Search, click **Save to library** on a result.
2. **Library** tab: your saved papers. Drop a PDF onto the upload box to add one.
3. Click **Open** on a paper to see its details, then **Generate summary** or ask a question (suggested questions are provided).
4. If extracted metadata looks wrong, use **Edit metadata**.

## Notes and limitations
- Each summary or question sends the paper's text (up to 300,000 characters) to the LLM, so large papers cost more tokens.
- Scanned PDFs without a text layer are rejected (no OCR).
- OpenAlex abstracts are sometimes missing or low quality; that comes from the data source.
- GROBID often misses the publication year; the app then guesses it from the first page, so check it.
- Tests are out of scope for this homework.
