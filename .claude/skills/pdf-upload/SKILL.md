---
name: pdf-upload
description: Work on PDF upload and metadata extraction (title, authors, year, abstract) using GROBID with a PyMuPDF fallback, no LLM. Use when uploads produce wrong metadata or text extraction fails.
---

# PDF upload

- Code: `backend/app/services/pdf.py`, `backend/app/services/metadata.py`; route `POST /api/papers/upload` in `backend/app/routers/papers.py` (multipart field `file`, 30 MB limit, read into memory).
- Flow: validate PDF type/size -> PyMuPDF (`import pymupdf`) extracts full text -> reject with 422 if under 200 chars (likely a scanned PDF) -> `extract_metadata` -> insert with `source = 'upload'` and the full text.
- Metadata uses NO LLM. `extract_metadata` first posts the PDF to GROBID (`GROBID_URL`, default `http://localhost:8070`, endpoint `/api/processHeaderDocument`) and parses the TEI XML (title, authors, publication date year, abstract). Use a short timeout.
- Fallback when GROBID is down or returns no title: PyMuPDF layout heuristics on page 1 via `get_text("dict")`: largest-font lines near the top (joined across wraps) = title; text after an "Abstract" heading until "Introduction"/next heading = abstract; most frequent 19xx/20xx = year, else PDF creation date; authors = lines between title and abstract minus affiliations/emails (weakest part, may be empty).
- Extraction can be wrong, so the UI lets users fix fields via `PATCH /api/papers/{id}`.
- GROBID gotchas: (1) send `Accept: application/xml`, otherwise `processHeaderDocument` returns BibTeX; (2) the missing-year case is common, so `extract_metadata` fills empty GROBID fields from the heuristics; (3) author names can pick up affiliation text on some layouts (e.g. "Rui Hkust"); (4) on Apple Silicon start it with `--platform linux/amd64 -e JAVA_TOOL_OPTIONS="-XX:-UseContainerSupport"` or the JVM crashes with a CgroupInfo NullPointerException (see README).
- Dependencies: `pymupdf`, `python-multipart`, `httpx`; parse TEI with `xml.etree.ElementTree` using the `http://www.tei-c.org/ns/1.0` namespace. Treat uploaded files as untrusted: never write them to a path derived from the filename.
- Test with a real paper PDF, with and without GROBID running.
