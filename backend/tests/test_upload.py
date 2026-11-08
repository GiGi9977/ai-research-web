import httpx


def upload(client, data, name="paper.pdf"):
    return client.post("/api/papers/upload", files={"file": (name, data, "application/pdf")})


def test_upload_pdf_without_grobid_uses_heuristics(client, no_network, sample_pdf):
    no_network.post("http://grobid.test/api/processHeaderDocument").mock(
        side_effect=httpx.ConnectError("no grobid")
    )
    r = upload(client, sample_pdf)
    assert r.status_code == 201
    body = r.json()
    assert body["source"] == "upload"
    assert body["title"] == "Deep Learning for Paper Summaries"
    assert body["hasFullText"] is True


def test_upload_rejects_non_pdf(client):
    r = upload(client, b"hello world", name="notes.txt")
    assert r.status_code == 400


def test_upload_rejects_unreadable_pdf(client):
    r = upload(client, b"%PDF-1.4 garbage")
    assert r.status_code == 422
