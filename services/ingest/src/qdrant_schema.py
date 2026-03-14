"""Qdrant collection schema for design_assets (Named Vectors)."""

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams

from src.config import settings

COLLECTION_NAME = "design_assets"
VECTOR_SIZE = settings.vector_size


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )


def create_collection_if_not_exists() -> None:
    """Create design_assets collection with named vectors (visual, textual)."""
    client = get_qdrant_client()
    collections = client.get_collections().collections
    if any(c.name == COLLECTION_NAME for c in collections):
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "visual": VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            "textual": VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        },
        optimizers_config=models.OptimizersConfigDiff(
            indexing_threshold=10000,
        ),
    )

    try:
        for field in ("category", "license_type", "brand", "content_hash"):
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
    except Exception:
        pass  # Indexes optional; search still works
