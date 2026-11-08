# Testing (HW2)

Automated tests for the FastAPI backend, generated and iteratively improved with a coding agent (Claude Code).

## Run the tests

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt        # pytest, pytest-cov, respx
python -m pytest                           # 112 passed, 5 xfailed
python -m pytest --cov --cov-report=term-missing   # line + branch coverage
python -m pytest --cov --cov-report=html           # HTML report in backend/htmlcov/
python tests/mutation/run_mutation.py              # fault-detection (mutation) score
```

The tests never touch the real database (`backend/data/library.db`), never read your real
`OPENAI_API_KEY` and make no network calls: every test gets a fresh SQLite file, settings are
overridden, and all `httpx` traffic is intercepted by `respx` (unmocked requests fail). OpenAI
calls are faked at the client level, since the OpenAI SDK uses `httpx2`.

## Layout

| File | Round | What it covers |
|---|---|---|
| `tests/conftest.py` | 0–1 | isolated DB, settings/network guards, PDF builder, fake DNS |
| `tests/test_health_search.py` | 0 | health, `/api/search` mapping, errors, limit cap |
| `tests/test_papers_api.py` | 0, 1 | save / duplicate / list / get / patch / delete, PDF fallback chain |
| `tests/test_upload.py` | 0 | PDF upload happy path and rejections |
| `tests/test_llm_api.py` | 0 | summary caching/refresh, Q&A storage, 404/422/503 |
| `tests/test_openalex.py` | 0 | abstract reconstruction |
| `tests/test_pdf_service.py` | 1 | text extraction, SSRF host check, PDF download limits/errors |
| `tests/test_pdf_sources.py` | 1 | DOI parsing, arXiv title match, Unpaywall fallback |
| `tests/test_metadata.py` | 1 | GROBID TEI parsing, layout heuristics, GROBID+heuristic merge |
| `tests/test_llm_service.py` | 1 | client config, prompt/context building, 20-message history window |
| `tests/test_llm_errors.py` | 1 | OpenAI error → HTTP status mapping, no API-key leakage, no partial writes |
| `tests/test_requirements.py` | 2 | README requirements: ordering, persistence, cascade delete, follow-up context, grounding, limits, startup |
| `tests/test_known_bugs.py` | 2 | 4 application bugs, `xfail(strict=True)` |
| `tests/mutation/` | eval | 30 seeded faults + runner |

`backend/test_results/` holds the raw outputs and snapshots of the suites after Round 0 and Round 1.

## Results by round

| Metric | Round 0 (initial) | Round 1 (coverage feedback) | Round 2 (requirements + faults) |
|---|---|---|---|
| Tests | 25 | 86 | 117 (112 pass + 5 xfail) |
| Pass rate | 25/25 | 86/86 | 112 pass, 5 expected failures (bugs) |
| Line + branch coverage | 70% | 97% | 99% |
| Lowest module | `pdf_sources.py` 23% | `metadata.py` 95% | `metadata.py`, `pdf_sources.py` 97% |
| Mutation score (30 seeded faults) | 10/30 (33%) | 26/30 (87%) | 30/30 (100%) |
| Real bugs detected | 0 | 0 | 4 |

Round strategies:
- **Round 0** – agent read the code and wrote API-level tests (TestClient, mocked network/LLM).
- **Round 1** – agent was given the coverage report (missing lines per module) and asked to cover the
  untested services: PDF download/SSRF, arXiv/Unpaywall, GROBID, LLM prompt building and error mapping.
- **Round 2** – agent was given the README requirements and asked to (a) strengthen weak assertions,
  (b) test each requirement end to end, (c) probe edge cases for bugs. Mutation testing was then used
  to compare fault-detection across rounds.

Mutants surviving Round 1 despite 97% coverage: upload size limit removed (M06), library order
reversed (M09), question stored unstripped (M12), `display_name` title fallback dropped (M29) —
those lines were executed but no assertion checked their effect.

## Bugs found (Round 2)

| ID | Bug | Detected by | Effect |
|---|---|---|---|
| BUG-1 | `PATCH /api/papers/{id}` with `{"authors": null}` stores NULL | `test_bug1_patch_authors_null_does_not_break_library` | that paper **and the entire library list** return HTTP 500 until the DB is fixed by hand |
| BUG-2 | Whitespace-only question passes validation (`min_length` is checked before `strip()`) | `test_bug2_blank_question_rejected` | an empty question is sent to OpenAI (cost) and stored in chat history |
| BUG-3 | Whitespace-only title accepted on save and edit | `test_bug3_blank_title_rejected_on_save/_on_edit` | papers with blank titles in the library |
| BUG-4 | SSRF guard checks only the first URL, but the download follows redirects | `test_bug4_redirect_to_private_host_is_blocked` | a public URL redirecting to `localhost`/private IPs is fetched |

These are marked `xfail(strict=True)`: the suite stays green while the bugs exist, and a test turns
into a failure as soon as its bug is fixed, as a reminder to remove the marker.
