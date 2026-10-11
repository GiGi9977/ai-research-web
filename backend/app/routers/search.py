from fastapi import APIRouter, HTTPException, Query

from app.services.openalex import SearchError, search_papers

router = APIRouter(prefix="/api")

MAX_LIMIT = 25


@router.get("/search")
async def search(q: str = Query(""), limit: int = Query(10, ge=1)):
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    try:
        return await search_papers(q, min(limit, MAX_LIMIT))
    except SearchError as e:
        raise HTTPException(status_code=502, detail=str(e))
