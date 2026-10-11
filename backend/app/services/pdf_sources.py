"""Fallback PDF locations for a paper when the provider's own pdfUrl fails."""
import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import httpx

from app.config import settings

log = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
UNPAYWALL_API = "https://api.unpaywall.org/v2/"
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def doi_from_url(url: str | None) -> str | None:
    if url and (m := re.search(r"doi\.org/(10\.\S+)$", url, re.I)):
        return m.group(1)
    return None


async def _arxiv_pdf(client: httpx.AsyncClient, title: str, doi: str | None) -> str | None:
    if doi and (m := re.match(r"10\.48550/arxiv\.(.+)$", doi, re.I)):
        return f"https://arxiv.org/pdf/{m.group(1)}"
    query = f'ti:"{title}"'
    resp = await client.get(ARXIV_API, params={"search_query": query, "max_results": 3})
    resp.raise_for_status()
    for entry in ET.fromstring(resp.text).findall("a:entry", ATOM):
        found = entry.findtext("a:title", default="", namespaces=ATOM)
        if _norm(found) == _norm(title):
            for link in entry.findall("a:link", ATOM):
                if link.get("title") == "pdf":
                    return link.get("href")
    return None


async def _unpaywall_pdf(client: httpx.AsyncClient, doi: str) -> str | None:
    resp = await client.get(
        UNPAYWALL_API + quote(doi, safe="/"), params={"email": settings.unpaywall_email}
    )
    resp.raise_for_status()
    loc = resp.json().get("best_oa_location") or {}
    return loc.get("url_for_pdf")


async def fallback_pdf_urls(title: str, source_url: str | None) -> list[str]:
    """Candidate PDF URLs from arXiv, then Unpaywall (only if UNPAYWALL_EMAIL is set)."""
    doi = doi_from_url(source_url)
    urls: list[str] = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        lookups = [_arxiv_pdf(client, title, doi)]
        if doi and settings.unpaywall_email:
            lookups.append(_unpaywall_pdf(client, doi))
        for lookup in lookups:
            try:
                if url := await lookup:
                    urls.append(url)
            except (httpx.HTTPError, ET.ParseError) as e:
                log.warning("PDF fallback lookup failed for %r: %s", title, e)
    return urls
