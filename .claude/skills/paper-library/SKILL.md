---
name: paper-library
description: Work on saving, listing, editing and deleting papers in the local SQLite library. Use when changing the database schema or the library API routes.
---

# Paper library

- Code: `backend/app/db.py` (engine, session, `create_all` on startup), `backend/app/models.py` (ORM), `backend/app/schemas.py` (Pydantic, camelCase aliases), routes in `backend/app/routers/papers.py`.
- Database: SQLite file at `backend/data/library.db` (git-ignored). Tables: `papers`, `messages` (chat history, FK `paper_id` with ON DELETE CASCADE; enable `PRAGMA foreign_keys=ON` per connection).
- Routes: `GET /api/papers` (no `full_text` in payload), `GET /api/papers/{id}` (includes messages), `POST /api/papers` (save a search result), `PATCH /api/papers/{id}` (edit title/authors/year/abstract), `DELETE /api/papers/{id}`.
- Saving dedupes on `external_id` (return the existing row). If the result has a `pdfUrl`, download the PDF and store its full text via `services/pdf.py` so summaries and Q&A use the real paper. If that fails (or there is no `pdfUrl`), `services/pdf_sources.py` tries fallbacks in order: arXiv (DOI `10.48550/arxiv.*` or exact title match via the arXiv API), then Unpaywall (only when `UNPAYWALL_EMAIL` is set; Unpaywall requires an email). The URL that worked replaces `pdf_url`. Downloads only fetch public http(s) hosts, max 30 MB, and must start with `%PDF`. Download or extraction failure is logged, not fatal.
- Schema changes: `create_all` does not migrate existing files. Delete `backend/data/` during development or add an `ALTER TABLE`.
- API responses use camelCase (Pydantic aliases); the database uses snake_case.
- Frontend: `LibraryPage.jsx`, `PaperDetail.jsx` (includes the edit-metadata form).
