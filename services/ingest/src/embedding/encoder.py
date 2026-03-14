"""Embedding encoder: CLIP (dev) or SigLIP-2 (prod) for visual + textual."""

from pathlib import Path
from typing import Any

from PIL import Image
from sentence_transformers import SentenceTransformer

from src.config import settings

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model_name)
    return _model


def encode_text(text: str) -> list[float]:
    """Encode text to vector (same size as visual)."""
    model = _get_model()
    emb = model.encode([text], convert_to_numpy=True)
    return emb[0].tolist()


def encode_image(image_path: str | Path) -> list[float]:
    """Encode image to vector. Supports CLIP-style models."""
    model = _get_model()
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    img = Image.open(path).convert("RGB")
    emb = model.encode([img], convert_to_numpy=True)
    return emb[0].tolist()


def encode_image_from_bytes(image_bytes: bytes) -> list[float]:
    """Encode image from in-memory bytes."""
    model = _get_model()
    from io import BytesIO

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    emb = model.encode([img], convert_to_numpy=True)
    return emb[0].tolist()
