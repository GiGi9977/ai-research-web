"""Extract title/authors/year/abstract from a PDF without an LLM.

GROBID (ML-based) is tried first; if it is down or finds no title, PyMuPDF layout
heuristics are used. Fields GROBID missed are filled in from the heuristics.
"""
import logging
import re
import xml.etree.ElementTree as ET
from collections import Counter

import httpx
import pymupdf

from app.config import settings

log = logging.getLogger(__name__)

TEI = {"t": "http://www.tei-c.org/ns/1.0"}
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")
AFFILIATION_WORDS = re.compile(
    r"univ|institut|department|dept|school|laborator|\blab\b|research|college|"
    r"corporation|\binc\b|\bltd\b|google|microsoft|meta ai|openai|deepmind|"
    r"@|http|www\.|abstract|arxiv|proceedings|conference|journal|copyright|\d{3,}",
    re.I,
)


def _text(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def parse_grobid_tei(xml: str) -> dict:
    root = ET.fromstring(xml)
    title = _text(root.find(".//t:titleStmt/t:title[@type='main']", TEI)) or _text(
        root.find(".//t:titleStmt/t:title", TEI)
    )
    authors = []
    for pers in root.findall(".//t:sourceDesc//t:analytic/t:author/t:persName", TEI):
        parts = [_text(f) for f in pers.findall("t:forename", TEI)] + [
            _text(pers.find("t:surname", TEI))
        ]
        if name := " ".join(p for p in parts if p):
            authors.append(name)
    year = None
    for date in root.findall(".//t:publicationStmt/t:date", TEI) + root.findall(
        ".//t:sourceDesc//t:date", TEI
    ):
        if m := YEAR_RE.search(date.get("when", "") or _text(date)):
            year = int(m.group(1))
            break
    abstract = _text(root.find(".//t:profileDesc/t:abstract", TEI)) or None
    return {"title": title, "authors": authors, "year": year, "abstract": abstract}


async def _grobid(pdf: bytes) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.grobid_url}/api/processHeaderDocument",
                files={"input": ("paper.pdf", pdf, "application/pdf")},
                data={"consolidateHeader": "0"},
                headers={"Accept": "application/xml"},  # default response is BibTeX
            )
            resp.raise_for_status()
        result = parse_grobid_tei(resp.text)
    except (httpx.HTTPError, ET.ParseError) as e:
        log.warning("GROBID unavailable or failed (%s); using heuristics", e)
        return None
    return result if result["title"] else None


# ---------- PyMuPDF heuristics ----------


def _page_lines(page) -> list[dict]:
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            lines.append(
                {
                    "text": " ".join("".join(s["text"] for s in spans).split()),
                    "size": max(s["size"] for s in spans),
                    "y": line["bbox"][1],
                }
            )
    return sorted(lines, key=lambda l: l["y"])


def _heuristic_title(lines: list[dict]) -> tuple[str, int]:
    """Largest-font lines near the top, joined across wraps. Returns (title, index after)."""
    # Titles have several words; this skips journal banners like "BMC Bioinformatics".
    candidates = [i for i, l in enumerate(lines[:40]) if len(l["text"].split()) >= 3]
    if not candidates:
        return "", 0
    biggest = max(lines[i]["size"] for i in candidates)
    start = next(i for i in candidates if lines[i]["size"] >= biggest - 0.5)
    end = start
    while end + 1 < len(lines) and abs(lines[end + 1]["size"] - biggest) <= 0.5:
        end += 1
    title = " ".join(l["text"] for l in lines[start : end + 1])
    return re.sub(r":(?=[A-Za-z])", ": ", title), end + 1  # "Foo:Bar" -> "Foo: Bar"


def _heuristic_authors(lines: list[dict], after: int) -> list[str]:
    authors = []
    for line in lines[after : after + 12]:
        if re.match(r"abstract\b", line["text"], re.I):
            break
        if AFFILIATION_WORDS.search(line["text"]):
            continue
        cleaned = re.sub(r"[∗*†‡§¶0-9]+", "", line["text"])
        for name in re.split(r",|\band\b|&|;", cleaned):
            words = name.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w[0].isalpha()):
                authors.append(" ".join(words))
    return list(dict.fromkeys(authors))


def _heuristic_abstract(text: str) -> str | None:
    m = re.search(
        r"(?is)\babstract\b[\s.:—\-–]*(.+?)"
        r"(?=\n\s*(?:\d+\.?|I\.)?\s*introduction\b|\n\s*(?:keywords?|index terms)\b|\Z)",
        text,
    )
    if not m:
        return None
    abstract = " ".join(m.group(1).split())
    abstract = re.sub(r"(\w)- (\w)", r"\1\2", abstract)  # undo hyphenation
    return abstract[:3000] or None


def _heuristic_year(text: str, doc) -> int | None:
    years = [int(y) for y in YEAR_RE.findall(text)]
    if years:
        return Counter(years).most_common(1)[0][0]
    if m := re.search(r"D:(\d{4})", doc.metadata.get("creationDate") or ""):
        return int(m.group(1))
    return None


def heuristic_metadata(pdf: bytes) -> dict:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        page = doc[0]
        lines = _page_lines(page)
        title, after = _heuristic_title(lines)
        first_pages = "\n".join(doc[i].get_text() for i in range(min(2, len(doc))))
        return {
            "title": title,
            "authors": _heuristic_authors(lines, after),
            "year": _heuristic_year(page.get_text(), doc),
            "abstract": _heuristic_abstract(first_pages),
        }


async def extract_metadata(pdf: bytes) -> dict:
    heuristic = heuristic_metadata(pdf)
    grobid = await _grobid(pdf)
    if not grobid:
        return heuristic
    return {k: grobid[k] or heuristic[k] for k in grobid}
