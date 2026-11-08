import pytest

from app.routers import papers as papers_router


@pytest.fixture(autouse=True)
def no_pdf_download(monkeypatch):
    async def none(*_a, **_k):
        return None

    async def no_urls(*_a, **_k):
        return []

    monkeypatch.setattr(papers_router, "download_pdf_text", none)
    monkeypatch.setattr(papers_router, "fallback_pdf_urls", no_urls)


PAPER = {
    "externalId": "https://openalex.org/W1",
    "title": "A Paper",
    "authors": ["A One", "B Two"],
    "year": 2020,
    "abstract": "An abstract.",
    "url": "https://doi.org/10.1/x",
}


def test_library_starts_empty(client):
    assert client.get("/api/papers").json() == []


def test_save_and_list(client):
    r = client.post("/api/papers", json=PAPER)
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "A Paper"
    assert body["hasFullText"] is False
    listed = client.get("/api/papers").json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


def test_save_duplicate_returns_existing(client):
    first = client.post("/api/papers", json=PAPER).json()
    r = client.post("/api/papers", json=PAPER)
    assert r.status_code == 200
    assert r.json()["id"] == first["id"]
    assert len(client.get("/api/papers").json()) == 1


def test_save_requires_title(client):
    r = client.post("/api/papers", json={**PAPER, "title": ""})
    assert r.status_code == 422


def test_save_with_pdf_stores_full_text(client, monkeypatch):
    async def text(url):
        return "full text of the paper"

    monkeypatch.setattr(papers_router, "download_pdf_text", text)
    r = client.post("/api/papers", json={**PAPER, "pdfUrl": "https://example.org/p.pdf"})
    assert r.status_code == 201
    assert r.json()["hasFullText"] is True


def test_get_paper_detail(client):
    pid = client.post("/api/papers", json=PAPER).json()["id"]
    r = client.get(f"/api/papers/{pid}")
    assert r.status_code == 200
    assert r.json()["summary"] is None
    assert r.json()["messages"] == []


def test_get_missing_paper_404(client):
    assert client.get("/api/papers/999").status_code == 404


def test_patch_metadata(client):
    pid = client.post("/api/papers", json=PAPER).json()["id"]
    r = client.patch(f"/api/papers/{pid}", json={"title": "New", "year": 2021})
    assert r.status_code == 200
    assert r.json()["title"] == "New"
    assert r.json()["year"] == 2021
    assert r.json()["authors"] == ["A One", "B Two"]


def test_delete_paper(client):
    pid = client.post("/api/papers", json=PAPER).json()["id"]
    assert client.delete(f"/api/papers/{pid}").status_code == 204
    assert client.get(f"/api/papers/{pid}").status_code == 404
    assert client.delete(f"/api/papers/{pid}").status_code == 404


# ---- Round 1 additions (uncovered branches from the coverage report) ----


def test_save_falls_back_to_alternative_pdf(client, monkeypatch):
    tried = []

    async def download(url):
        tried.append(url)
        return "text from mirror" if url == "https://mirror/2.pdf" else None

    async def candidates(title, url):
        assert (title, url) == (PAPER["title"], PAPER["url"])
        return ["https://mirror/1.pdf", "https://mirror/2.pdf", "https://mirror/3.pdf"]

    monkeypatch.setattr(papers_router, "download_pdf_text", download)
    monkeypatch.setattr(papers_router, "fallback_pdf_urls", candidates)
    r = client.post("/api/papers", json={**PAPER, "pdfUrl": "https://broken/p.pdf"})
    assert r.status_code == 201
    assert r.json()["pdfUrl"] == "https://mirror/2.pdf"
    assert r.json()["hasFullText"] is True
    assert tried == ["https://broken/p.pdf", "https://mirror/1.pdf", "https://mirror/2.pdf"]


def test_patch_null_title_is_ignored(client):
    pid = client.post("/api/papers", json=PAPER).json()["id"]
    r = client.patch(f"/api/papers/{pid}", json={"title": None, "abstract": None})
    assert r.status_code == 200
    assert r.json()["title"] == "A Paper"
    assert r.json()["abstract"] is None
