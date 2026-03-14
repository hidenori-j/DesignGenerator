"""Async MinIO (S3-compatible) storage client using aioboto3."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import aioboto3

from src.config import settings

logger = logging.getLogger(__name__)

_session: aioboto3.Session | None = None


def _get_session() -> aioboto3.Session:
    global _session
    if _session is None:
        _session = aioboto3.Session(
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
        )
    return _session


def _endpoint_url() -> str:
    scheme = "https" if settings.minio_use_ssl else "http"
    return f"{scheme}://{settings.minio_endpoint}"


async def upload_generated_image(
    image_bytes: bytes,
    *,
    job_id: str,
    content_type: str = "image/png",
) -> str:
    """Upload generated image to MinIO and return a presigned URL.

    Falls back to returning an empty string if MinIO is unavailable.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    key = f"generated/{ts}_{job_id}_{uuid.uuid4().hex[:8]}.png"
    bucket = settings.minio_bucket_generated

    try:
        session = _get_session()
        async with session.client(
            "s3",
            endpoint_url=_endpoint_url(),
            region_name="us-east-1",
        ) as s3:
            await s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=image_bytes,
                ContentType=content_type,
            )

            presigned = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=3600 * 24,
            )

        logger.info("Image uploaded to MinIO: %s/%s (%d bytes)", bucket, key, len(image_bytes))
        return presigned

    except Exception:
        logger.warning(
            "[STORAGE] MinIO is unavailable. Generated image will not be persisted. "
            "Ensure Docker (MinIO) is running or check MINIO_* settings in .env."
        )
        return ""
