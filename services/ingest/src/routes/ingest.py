import logging

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from src.embedding.encoder import encode_text
from src.pipeline.run import run_ingest
from src.qdrant_schema import COLLECTION_NAME, create_collection_if_not_exists, get_qdrant_client

logger = logging.getLogger(__name__)

router = APIRouter()


class EncodeRequest(BaseModel):
    text: str


class EncodeResponse(BaseModel):
    vector: list[float]
    size: int


@router.post("/encode", response_model=EncodeResponse)
async def encode_query(req: EncodeRequest) -> EncodeResponse:
    """Encode text to vector (same model as ingest). Used by Agent for search."""
    vec = encode_text(req.text)
    return EncodeResponse(vector=vec, size=len(vec))


@router.post("/ingest")
async def ingest_image(
    file: UploadFile,
    category: str = "unknown",
    license_type: str = "internal",
    dedup: str = "skip",
) -> dict[str, str]:
    """Upload one image: embed (visual + text) and upsert to Qdrant."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Image file required")
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")
    try:
        result = await run_ingest(
            content,
            file.filename or "unknown",
            category=category,
            license_type=license_type,
            dedup=dedup,
        )
        return {
            "status": "ok",
            "asset_id": result["asset_id"],
            "filename": file.filename or "unknown",
            "message": result.get("message", "Image ingested and indexed"),
            "skipped": str(result.get("skipped", False)),
        }
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@router.post("/ingest/batch")
async def ingest_batch(
    files: list[UploadFile],
    dedup: str = "skip",
) -> dict[str, object]:
    """Ingest multiple images; returns list of asset_ids."""
    results: list[dict[str, str]] = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            results.append({"filename": f.filename or "?", "error": "not an image"})
            continue
        content = await f.read()
        if not content:
            results.append({"filename": f.filename or "?", "error": "empty file"})
            continue
        try:
            result = await run_ingest(content, f.filename or "unknown", dedup=dedup)
            results.append({
                "filename": f.filename or "?",
                "asset_id": result["asset_id"],
                "skipped": str(result.get("skipped", False)),
            })
        except Exception as e:
            results.append({"filename": f.filename or "?", "error": str(e)})
    return {"status": "ok", "count": len(results), "results": results}


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------


@router.get("/collection/stats")
async def collection_stats() -> dict[str, object]:
    """Return Qdrant collection statistics."""
    try:
        client = get_qdrant_client()
        info = client.get_collection(COLLECTION_NAME)
        return {
            "collection": COLLECTION_NAME,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "status": info.status.value,
        }
    except Exception as e:
        logger.warning("Failed to get collection stats: %s", e)
        return {
            "collection": COLLECTION_NAME,
            "points_count": 0,
            "vectors_count": 0,
            "status": "unavailable",
            "error": str(e),
        }


@router.delete("/collection/reset")
async def reset_collection() -> dict[str, str]:
    """Delete and recreate the design_assets collection."""
    try:
        client = get_qdrant_client()
        client.delete_collection(COLLECTION_NAME)
        logger.info("Deleted collection: %s", COLLECTION_NAME)
    except Exception:
        logger.info("Collection %s did not exist, creating fresh", COLLECTION_NAME)
    create_collection_if_not_exists()
    logger.info("Recreated collection: %s", COLLECTION_NAME)
    return {"status": "ok", "message": f"Collection '{COLLECTION_NAME}' has been reset"}
