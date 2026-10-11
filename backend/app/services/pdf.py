import ipaddress
import logging
import socket
from urllib.parse import urlparse

import pymupdf
import httpx

log = logging.getLogger(__name__)

MAX_PDF_BYTES = 30 * 1024 * 1024
MIN_TEXT_CHARS = 200


class PdfError(Exception):
    pass


def extract_text(data: bytes) -> str:
    """Extract text from PDF bytes. Raises PdfError if unreadable or too short (scanned)."""
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            text = "\n".join(page.get_text() for page in doc).strip()
    except Exception as e:
        raise PdfError(f"Could not read PDF: {e}") from e
    if len(text) < MIN_TEXT_CHARS:
        raise PdfError("PDF has too little extractable text (is it a scanned image?)")
    return text


def _is_public_host(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    return all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


async def download_pdf_text(url: str) -> str | None:
    """Download a PDF and extract its text. Returns None (and logs) on any failure."""
    if not _is_public_host(url):
        log.warning("Refusing to download PDF from non-public URL: %s", url)
        return None
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                chunks, size = [], 0
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_PDF_BYTES:
                        log.warning("PDF too large, skipping: %s", url)
                        return None
                    chunks.append(chunk)
        data = b"".join(chunks)
        if not data.startswith(b"%PDF"):
            log.warning("URL did not return a PDF: %s", url)
            return None
        return extract_text(data)
    except (httpx.HTTPError, PdfError) as e:
        log.warning("PDF download/extract failed for %s: %s", url, e)
        return None
