import httpx

OPENALEX = "https://api.openalex.org/works"


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_search_requires_query(client):
    r = client.get("/api/search", params={"q": "   "})
    assert r.status_code == 400


def test_search_returns_mapped_results(client, no_network):
    no_network.get(OPENALEX).respond(
        json={
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "doi": "https://doi.org/10.1/abc",
                    "title": "Attention Is All You Need",
                    "publication_year": 2017,
                    "authorships": [{"author": {"display_name": "Ashish Vaswani"}}],
                    "abstract_inverted_index": {"Transformers": [0], "rock": [1]},
                    "best_oa_location": {"pdf_url": "https://arxiv.org/pdf/1706.03762"},
                }
            ]
        }
    )
    r = client.get("/api/search", params={"q": "attention"})
    assert r.status_code == 200
    [paper] = r.json()
    assert paper["externalId"] == "https://openalex.org/W1"
    assert paper["title"] == "Attention Is All You Need"
    assert paper["authors"] == ["Ashish Vaswani"]
    assert paper["year"] == 2017
    assert paper["abstract"] == "Transformers rock"
    assert paper["url"] == "https://doi.org/10.1/abc"
    assert paper["pdfUrl"] == "https://arxiv.org/pdf/1706.03762"


def test_search_limit_is_capped(client, no_network):
    route = no_network.get(OPENALEX).respond(json={"results": []})
    r = client.get("/api/search", params={"q": "x", "limit": 100})
    assert r.status_code == 200
    assert route.calls.last.request.url.params["per-page"] == "25"


def test_search_upstream_error_returns_502(client, no_network):
    no_network.get(OPENALEX).mock(side_effect=httpx.ConnectError("down"))
    r = client.get("/api/search", params={"q": "x"})
    assert r.status_code == 502
