import httpx

from app.config import settings

OPENALEX_URL = "https://api.openalex.org/works"
SELECT_FIELDS = (
    "id,doi,title,display_name,publication_year,authorships,"
    "abstract_inverted_index,primary_location,open_access,best_oa_location"
)


class SearchError(Exception):
    pass


def abstract_from_index(index: dict | None) -> str | None:
    if not index:
        return None
    words: dict[int, str] = {}
    for word, positions in index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words)) or None


def _to_result(work: dict) -> dict:
    best_oa = work.get("best_oa_location") or {}
    primary = work.get("primary_location") or {}
    url = work.get("doi") or primary.get("landing_page_url") or work.get("id")
    return {
        "externalId": work["id"],
        "source": "openalex",
        "title": work.get("title") or work.get("display_name") or "(untitled)",
        "authors": [
            a["author"]["display_name"]
            for a in work.get("authorships", [])
            if a.get("author", {}).get("display_name")
        ],
        "year": work.get("publication_year"),
        "abstract": abstract_from_index(work.get("abstract_inverted_index")),
        "url": url,
        "pdfUrl": best_oa.get("pdf_url"),
    }


async def search_papers(query: str, limit: int = 10) -> list[dict]:
    params = {"search": query, "per-page": limit, "select": SELECT_FIELDS}
    if settings.openalex_mailto:
        params["mailto"] = settings.openalex_mailto
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(OPENALEX_URL, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as e:
        raise SearchError(f"OpenAlex request failed: {e}") from e
    return [_to_result(w) for w in resp.json().get("results", [])]
