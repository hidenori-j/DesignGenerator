"""HuggingFace dataset loader for design reference images."""

import logging
from io import BytesIO

from PIL import Image

from datasets import load_dataset
from src.config import settings
from src.scrapers.base import CollectedImage

logger = logging.getLogger(__name__)

DEFAULT_DATASETS = [
    {
        "repo": "ILSVRC/imagenet-1k",
        "split": "validation",
        "category": "stock_photo",
        "max_samples": 200,
    },
    {
        "repo": "detection-datasets/fashionpedia",
        "split": "val",
        "category": "fashion_design",
        "max_samples": 200,
    },
]


async def load_hf_dataset(
    repo: str,
    *,
    split: str = "train",
    category: str = "design_reference",
    max_samples: int = 500,
    image_column: str = "image",
) -> list[CollectedImage]:
    """
    Download images from a HuggingFace dataset and save locally.
    Returns list of CollectedImage items for downstream ingest.
    """
    output_dir = settings.download_dir / "huggingface" / repo.replace("/", "_")
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[hf] Loading dataset %s (split=%s, max=%d)", repo, split, max_samples)

    try:
        ds = load_dataset(repo, split=split, streaming=True, trust_remote_code=False)
    except Exception:
        logger.error("[hf] Failed to load dataset %s", repo, exc_info=True)
        return []

    results: list[CollectedImage] = []
    count = 0

    for sample in ds:
        if count >= max_samples:
            break

        try:
            img = sample.get(image_column)
            if img is None:
                continue

            if isinstance(img, Image.Image):
                pil_img = img
            elif isinstance(img, dict) and "bytes" in img:
                pil_img = Image.open(BytesIO(img["bytes"]))
            else:
                continue

            if pil_img.width < 200 or pil_img.height < 200:
                continue

            filename = f"{repo.replace('/', '_')}_{split}_{count:06d}.png"
            filepath = output_dir / filename
            pil_img.save(filepath, "PNG")

            results.append(
                CollectedImage(
                    filepath=filepath,
                    source_url=f"https://huggingface.co/datasets/{repo}",
                    source_domain="huggingface.co",
                    page_url=f"https://huggingface.co/datasets/{repo}",
                    title=f"{repo} sample #{count}",
                    tags=[category, "huggingface"],
                    category=category,
                    license_type="dataset_license",
                )
            )
            count += 1

        except Exception:
            logger.debug("[hf] Error processing sample %d", count, exc_info=True)
            continue

    logger.info("[hf] Collected %d images from %s", len(results), repo)
    return results


async def load_all_default_datasets() -> list[CollectedImage]:
    """Load all pre-configured HuggingFace datasets."""
    all_results: list[CollectedImage] = []
    for cfg in DEFAULT_DATASETS:
        items = await load_hf_dataset(
            cfg["repo"],
            split=cfg["split"],
            category=cfg["category"],
            max_samples=cfg["max_samples"],
        )
        all_results.extend(items)
    return all_results
