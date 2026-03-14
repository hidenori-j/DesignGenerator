"""Single-image ingest pipeline: embed and upsert to Qdrant."""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qdrant_client.http import models

from src.cache import content_hash, get_cached_embedding, set_cached_embedding
from src.embedding.encoder import encode_image_from_bytes, encode_text
from src.qdrant_schema import COLLECTION_NAME, get_qdrant_client

logger = logging.getLogger(__name__)


def _default_caption(filename: str) -> str:
    """Placeholder caption until VLM (Qwen2.5-VL) is used."""
    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    return f"デザイン画像: {stem}"


def _find_existing_by_hash(client: Any, c_hash: str) -> str | None:
    """Return the point ID if a point with the same content_hash exists."""
    try:
        results, _next = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="content_hash",
                        match=models.MatchValue(value=c_hash),
                    )
                ]
            ),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        if results:
            return str(results[0].id)
    except Exception:
        pass
    return None


async def run_ingest(
    image_bytes: bytes,
    filename: str,
    *,
    category: str = "unknown",
    style_tags: list[str] | None = None,
    license_type: str = "internal",
    brand: str | None = None,
    use_cache: bool = True,
    dedup: str = "skip",
) -> dict[str, Any]:
    """
    Ingest one image: encode visual + textual, upsert to Qdrant.

    dedup controls duplicate handling based on content_hash:
      - "skip": if the same image already exists, skip and return existing ID
      - "overwrite": always upsert (replace existing point if hash matches)

    Returns dict with asset_id, skipped flag, and message.
    """
    style_tags = style_tags or []
    c_hash = content_hash(image_bytes)
    client = get_qdrant_client()

    if dedup == "skip":
        existing_id = _find_existing_by_hash(client, c_hash)
        if existing_id:
            logger.info("Duplicate skipped: %s (existing=%s)", filename, existing_id)
            return {
                "asset_id": existing_id,
                "skipped": True,
                "message": f"Duplicate skipped (existing asset: {existing_id})",
            }

    existing_id_for_overwrite = None
    if dedup == "overwrite":
        existing_id_for_overwrite = _find_existing_by_hash(client, c_hash)

    asset_id = existing_id_for_overwrite or str(uuid.uuid4())

    if use_cache:
        cached = await get_cached_embedding(c_hash)
        if cached:
            visual_vec = cached
            textual_vec = encode_text(_default_caption(filename))
        else:
            visual_vec = encode_image_from_bytes(image_bytes)
            textual_vec = encode_text(_default_caption(filename))
            await set_cached_embedding(c_hash, visual_vec)
    else:
        visual_vec = encode_image_from_bytes(image_bytes)
        textual_vec = encode_text(_default_caption(filename))

    payload = {
        "category": category,
        "style_tags": style_tags,
        "color_palette": [],
        "typography": "",
        "brand": brand or "",
        "resolution": "",
        "license_type": license_type,
        "content_hash": c_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "caption": _default_caption(filename),
    }

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=asset_id,
                vector={
                    "visual": visual_vec,
                    "textual": textual_vec,
                },
                payload=payload,
            )
        ],
    )
    logger.info("Ingested asset %s (%s)", asset_id, filename)
    return {"asset_id": asset_id, "skipped": False, "message": "Image ingested and indexed"}
