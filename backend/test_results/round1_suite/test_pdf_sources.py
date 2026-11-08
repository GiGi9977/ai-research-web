"""Round 1: services/pdf_sources.py (arXiv / Unpaywall fallbacks)."""
import httpx
import pytest

from app.config import settings
from app.services.pdf_sources import doi_from_url, fallback_pdf_urls

pytestmark = pytest.mark.anyio

ARXIV = "https://export.arxiv.org/api/query"


def atom(*entries):
    body = "".join(
        f'<entry><title>{t}</title><link title="pdf" href="{h}"/>'
        f'<link rel="alternate" href="{h}abs"/></entry>'
        for t, h in entries
    )
    return f'<feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'


@pytest.mark.parametrize(
    "url, doi",
    [
        ("https://doi.org/10.1145/3292500.3330701", "10.1145/3292500.3330701"),
        ("https://DOI.org/10.48550/arXiv.1706.03762", "10.48550/arXiv.1706.03762"),
        ("https://openalex.org/W123", None),
        (None, None),
        ("", None),
    ],
)
def test_doi_from_url(url, doi):
    assert doi_from_url(url) == doi


async def test_arxiv_doi_shortcut_skips_search(no_network):
    route = no_network.get(ARXIV)
    urls = await fallback_pdf_urls("Whatever", "https://doi.org/10.48550/arXiv.1706.03762")
    assert urls == ["https://arxiv.org/pdf/1706.03762"]
    assert not route.called


async def test_arxiv_title_match_ignores_case_and_punctuation(no_network):
    route = no_network.get(ARXIV).respond(
        text=atom(
            ("Something Else", "http://arxiv.org/pdf/1"),
            ("Attention is all you need!", "http://arxiv.org/pdf/1706.03762v7"),
        )
    )
    urls = await fallback_pdf_urls("Attention Is All You Need", None)
    assert urls == ["http://arxiv.org/pdf/1706.03762v7"]
    assert route.calls.last.request.url.params["search_query"] == 'ti:"Attention Is All You Need"'


async def test_arxiv_no_exact_match(no_network):
    no_network.get(ARXIV).respond(text=atom(("Attention Is Not All You Need", "http://x/pdf")))
    assert await fallback_pdf_urls("Attention Is All You Need", None) == []


async def test_unpaywall_used_only_with_email(no_network, monkeypatch):
    no_network.get(ARXIV).respond(text=atom())
    unpaywall = no_network.get("https://api.unpaywall.org/v2/10.1/abc").respond(
        json={"best_oa_location": {"url_for_pdf": "https://repo.org/abc.pdf"}}
    )
    assert await fallback_pdf_urls("T", "https://doi.org/10.1/abc") == []
    assert not unpaywall.called

    monkeypatch.setattr(settings, "unpaywall_email", "me@example.org")
    assert await fallback_pdf_urls("T", "https://doi.org/10.1/abc") == ["https://repo.org/abc.pdf"]
    assert unpaywall.calls.last.request.url.params["email"] == "me@example.org"


async def test_unpaywall_without_oa_location(no_network, monkeypatch):
    monkeypatch.setattr(settings, "unpaywall_email", "me@example.org")
    no_network.get(ARXIV).respond(text=atom())
    no_network.get("https://api.unpaywall.org/v2/10.1/abc").respond(json={"best_oa_location": None})
    assert await fallback_pdf_urls("T", "https://doi.org/10.1/abc") == []


async def test_lookup_failures_are_swallowed(no_network, monkeypatch):
    monkeypatch.setattr(settings, "unpaywall_email", "me@example.org")
    no_network.get(ARXIV).respond(text="not xml <")
    no_network.get("https://api.unpaywall.org/v2/10.1/abc").respond(
        json={"best_oa_location": {"url_for_pdf": "https://repo.org/abc.pdf"}}
    )
    # arXiv fails to parse, Unpaywall still contributes.
    assert await fallback_pdf_urls("T", "https://doi.org/10.1/abc") == ["https://repo.org/abc.pdf"]


async def test_arxiv_http_error(no_network):
    no_network.get(ARXIV).mock(side_effect=httpx.ConnectError("down"))
    assert await fallback_pdf_urls("T", None) == []
