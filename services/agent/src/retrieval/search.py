"""Qdrant search using query vector from Ingest service."""

from __future__ import annotations

import logging

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "design_assets"


def _get_qdrant() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )


def _encode_query(text: str) -> list[float]:
    """Get query vector from Ingest service."""
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{settings.ingest_service_url.rstrip('/')}/api/v1/encode",
            json={"text": text},
        )
        r.raise_for_status()
        data = r.json()
        return data["vector"]


def _build_filter(
    *,
    category: str | None = None,
    license_type: str | None = None,
    style_tags: list[str] | None = None,
) -> models.Filter | None:
    """Build Qdrant filter from optional parameters."""
    conditions: list[models.FieldCondition] = []

    if category:
        conditions.append(
            models.FieldCondition(key="category", match=models.MatchValue(value=category))
        )
    if license_type:
        conditions.append(
            models.FieldCondition(key="license_type", match=models.MatchValue(value=license_type))
        )
    if style_tags:
        for tag in style_tags:
            conditions.append(
                models.FieldCondition(key="style_tags", match=models.MatchValue(value=tag))
            )

    return models.Filter(must=conditions) if conditions else None


def search(
    query: str,
    *,
    category: str | None = None,
    limit: int = 20,
) -> list[tuple[str, float, dict]]:
    """
    Search design_assets by text query (textual vector only).
    Returns list of (id, score, payload).
    """
    vector = _encode_query(query)
    client = _get_qdrant()
    filter_ = _build_filter(category=category)

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=("textual", vector),
        query_filter=filter_,
        limit=limit,
        with_payload=True,
    )

    return [(hit.id, hit.score or 0.0, hit.payload or {}) for hit in results]


def hybrid_search(
    query: str,
    *,
    category: str | None = None,
    license_type: str | None = None,
    style_tags: list[str] | None = None,
    limit: int = 20,
    visual_weight: float = 0.4,
    textual_weight: float = 0.6,
) -> list[tuple[str, float, dict]]:
    """
    Hybrid search using both textual and visual named vectors.
    Merges results from both searches using weighted score fusion.
    """
    vector = _encode_query(query)
    client = _get_qdrant()
    filter_ = _build_filter(category=category, license_type=license_type, style_tags=style_tags)

    fetch_limit = limit * 2

    textual_results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=("textual", vector),
        query_filter=filter_,
        limit=fetch_limit,
        with_payload=True,
    )

    visual_results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=("visual", vector),
        query_filter=filter_,
        limit=fetch_limit,
        with_payload=True,
    )

    scores: dict[str, float] = {}
    payloads: dict[str, dict] = {}

    for hit in textual_results:
        hit_id = str(hit.id)
        scores[hit_id] = (hit.score or 0.0) * textual_weight
        payloads[hit_id] = hit.payload or {}

    for hit in visual_results:
        hit_id = str(hit.id)
        visual_score = (hit.score or 0.0) * visual_weight
        scores[hit_id] = scores.get(hit_id, 0.0) + visual_score
        if hit_id not in payloads:
            payloads[hit_id] = hit.payload or {}

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:limit]

    return [(id_, scores[id_], payloads[id_]) for id_ in sorted_ids]


def multi_query_search(
    queries: list[str],
    *,
    category: str | None = None,
    license_type: str | None = None,
    limit: int = 20,
) -> list[tuple[str, float, dict]]:
    """
    Execute multiple search queries and merge results.
    Used by the RAG pipeline to search with decomposed queries.
    """
    all_scores: dict[str, float] = {}
    all_payloads: dict[str, dict] = {}

    for q in queries:
        try:
            results = hybrid_search(
                q, category=category, license_type=license_type, limit=limit
            )
            for id_, score, payload in results:
                if id_ not in all_scores or score > all_scores[id_]:
                    all_scores[id_] = score
                    all_payloads[id_] = payload
        except Exception:
            logger.warning("Search failed for query: %s", q, exc_info=True)

    sorted_ids = sorted(all_scores, key=lambda x: all_scores[x], reverse=True)[:limit]
    return [(id_, all_scores[id_], all_payloads[id_]) for id_ in sorted_ids]
