"""Client to push collected images into the Ingest service."""

import logging
from pathlib import Path

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


async def push_to_ingest(
    image_path: Path,
    *,
    category: str = "unknown",
    license_type: str = "copyrighted_reference",
    source_url: str = "",
    source_domain: str = "",
    dedup: str = "skip",
) -> dict:
    """Upload a collected image to the Ingest service with governance metadata."""
    mime = _MIME_BY_EXT.get(image_path.suffix.lower(), "image/png")
    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(image_path, "rb") as f:
            resp = await client.post(
                f"{settings.ingest_service_url}/api/v1/ingest",
                files={"file": (image_path.name, f, mime)},
                data={
                    "category": category,
                    "license_type": license_type,
                    "dedup": dedup,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Ingested %s -> %s", image_path.name, data.get("asset_id", "?"))
        return data
