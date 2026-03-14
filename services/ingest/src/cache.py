"""Redis cache for ingest (e.g. avoid re-embedding same content)."""

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as redis

from src.config import settings

logger = logging.getLogger(__name__)

CACHE_PREFIX = "ingest:"
DEFAULT_TTL = 86400  # 24h


def _key(prefix: str, id_or_hash: str) -> str:
    return f"{CACHE_PREFIX}{prefix}:{id_or_hash}"


async def get_cached_embedding(content_hash: str) -> list[float] | None:
    """Return cached embedding if present."""
    r = redis.from_url(settings.redis_url)
    try:
        raw = await r.get(_key("emb", content_hash))
        if raw:
            return json.loads(raw)
    finally:
        await r.close()
    return None


async def set_cached_embedding(content_hash: str, vector: list[float], ttl: int = DEFAULT_TTL) -> None:
    """Cache embedding by content hash."""
    r = redis.from_url(settings.redis_url)
    try:
        await r.set(_key("emb", content_hash), json.dumps(vector), ex=ttl)
    finally:
        await r.close()


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:32]
