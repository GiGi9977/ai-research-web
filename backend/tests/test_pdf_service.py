"""Round 1: services/pdf.py (text extraction, SSRF guard, PDF download)."""
import httpx
import pytest

from app.services import pdf
from app.services.pdf import PdfError, download_pdf_text, extract_text

from .conftest import BODY, make_pdf

pytestmark = pytest.mark.anyio


def test_extract_text_returns_page_text(sample_pdf):
    text = extract_text(sample_pdf)
    assert "Deep Learning for Paper Summaries" in text
    assert "machine learning research" in text


def test_extract_text_rejects_short_text():
    with pytest.raises(PdfError, match="too little extractable text"):
        extract_text(make_pdf([("Only a title", 20)]))


def test_extract_text_rejects_corrupt_bytes():
    with pytest.raises(PdfError, match="Could not read PDF"):
        extract_text(b"%PDF-1.4 this is not really a pdf")


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.org/paper.pdf", True),
        ("http://example.org/paper.pdf", True),
        ("ftp://example.org/paper.pdf", False),
        ("file:///etc/passwd", False),
        ("https:///no-host", False),
        ("http://localhost/paper.pdf", False),
        ("http://intranet.internal/paper.pdf", False),
        ("http://meta.internal/latest/meta-data", False),
        ("http://nxdomain.test/paper.pdf", False),
    ],
)
def test_is_public_host(fake_dns, url, expected):
    assert pdf._is_public_host(url) is expected


async def test_download_returns_text(fake_dns, no_network, sample_pdf):
    no_network.get("https://example.org/p.pdf").respond(content=sample_pdf)
    text = await download_pdf_text("https://example.org/p.pdf")
    assert text is not None and "Deep Learning for Paper Summaries" in text


async def test_download_refuses_private_host_without_request(fake_dns, no_network):
    route = no_network.get("http://localhost/p.pdf").respond(content=b"%PDF")
    assert await download_pdf_text("http://localhost/p.pdf") is None
    assert not route.called


async def test_download_non_pdf_response(fake_dns, no_network):
    no_network.get("https://example.org/p.pdf").respond(content=b"<html>paywall</html>")
    assert await download_pdf_text("https://example.org/p.pdf") is None


async def test_download_http_error(fake_dns, no_network):
    no_network.get("https://example.org/p.pdf").respond(status_code=404)
    assert await download_pdf_text("https://example.org/p.pdf") is None


async def test_download_network_error(fake_dns, no_network):
    no_network.get("https://example.org/p.pdf").mock(side_effect=httpx.ConnectTimeout("t"))
    assert await download_pdf_text("https://example.org/p.pdf") is None


async def test_download_too_large(fake_dns, no_network, monkeypatch, sample_pdf):
    monkeypatch.setattr(pdf, "MAX_PDF_BYTES", 100)
    no_network.get("https://example.org/p.pdf").respond(content=sample_pdf)
    assert await download_pdf_text("https://example.org/p.pdf") is None


async def test_download_scanned_pdf(fake_dns, no_network):
    no_network.get("https://example.org/p.pdf").respond(content=make_pdf([("x", 10)]))
    assert await download_pdf_text("https://example.org/p.pdf") is None
