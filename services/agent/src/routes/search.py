from fastapi import APIRouter, HTTPException, Query

from src.retrieval.search import search

router = APIRouter()


@router.get("/search")
async def search_assets(
    query: str = Query(..., min_length=1),
    category: str | None = None,
    style_tags: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Search design assets via Qdrant (query encoded by Ingest service)."""
    try:
        hits = search(query, category=category, limit=limit)
    except Exception as e:
        raise HTTPException(502, f"Search failed: {e}") from e

    results = []
    for asset_id, score, payload in hits:
        caption = payload.get("caption") or payload.get("filename") or ""
        results.append({
            "id": asset_id,
            "score": round(score, 4),
            "category": payload.get("category") or "unknown",
            "style_tags": payload.get("style_tags") or [],
            "caption": caption,
            "thumbnail_url": payload.get("thumbnail_url") or "",
        })

    return {
        "results": results,
        "total": len(results),
        "query": query,
    }
