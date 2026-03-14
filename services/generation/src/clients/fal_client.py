"""Fal.ai FLUX.2 Pro async client with mock fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

FAL_API_BASE = "https://fal.run"
FLUX_MODEL = "fal-ai/flux-pro/v1.1"

MOCK_IMAGE_URL = (
    "https://placehold.co/1920x1080/1a1a2e/eee"
    "?text=Generated+Design+(MOCK)&font=noto-sans-jp"
)


@dataclass
class FalGenerationResult:
    image_url: str
    image_bytes: bytes | None
    width: int
    height: int
    seed: int
    is_mock: bool
    model: str


async def generate_with_fal(
    positive_prompt: str,
    negative_prompt: str = "",
    style_prompt: str = "",
    width: int = 1920,
    height: int = 1080,
    num_inference_steps: int = 28,
    guidance_scale: float = 3.5,
    seed: int | None = None,
) -> FalGenerationResult:
    """Call Fal.ai FLUX.2 Pro API. Falls back to mock if API key is missing."""
    if not settings.fal_ai_api_key:
        logger.warning(
            "[MOCK] FAL_AI_API_KEY is missing. Falling back to MOCK image. "
            "Set FAL_AI_API_KEY in .env to enable real generation."
        )
        return FalGenerationResult(
            image_url=MOCK_IMAGE_URL,
            image_bytes=None,
            width=width,
            height=height,
            seed=0,
            is_mock=True,
            model=FLUX_MODEL,
        )

    full_prompt = positive_prompt
    if style_prompt:
        full_prompt = f"{style_prompt}, {full_prompt}"

    payload: dict = {
        "prompt": full_prompt,
        "image_size": {"width": width, "height": height},
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "num_images": 1,
        "enable_safety_checker": True,
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if seed is not None:
        payload["seed"] = seed

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            resp = await client.post(
                f"{FAL_API_BASE}/{FLUX_MODEL}",
                headers={
                    "Authorization": f"Key {settings.fal_ai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning(
                    "[RATE_LIMIT] Fal.ai rate limit exceeded. Falling back to MOCK image."
                )
            elif e.response.status_code in (401, 403):
                logger.warning(
                    "[AUTH_ERROR] Fal.ai API key is invalid or expired. "
                    "Falling back to MOCK image."
                )
            else:
                logger.warning(
                    "[API_ERROR] Fal.ai returned %d: %s. Falling back to MOCK image.",
                    e.response.status_code,
                    e.response.text[:200],
                )
            return FalGenerationResult(
                image_url=MOCK_IMAGE_URL,
                image_bytes=None,
                width=width,
                height=height,
                seed=0,
                is_mock=True,
                model=FLUX_MODEL,
            )
        except httpx.RequestError as e:
            logger.warning(
                "[NETWORK_ERROR] Failed to reach Fal.ai: %s. Falling back to MOCK image.", e
            )
            return FalGenerationResult(
                image_url=MOCK_IMAGE_URL,
                image_bytes=None,
                width=width,
                height=height,
                seed=0,
                is_mock=True,
                model=FLUX_MODEL,
            )

    images = data.get("images", [])
    if not images:
        logger.warning("[API_ERROR] Fal.ai returned no images. Falling back to MOCK.")
        return FalGenerationResult(
            image_url=MOCK_IMAGE_URL,
            image_bytes=None,
            width=width,
            height=height,
            seed=0,
            is_mock=True,
            model=FLUX_MODEL,
        )

    image_info = images[0]
    remote_url = image_info.get("url", "")
    result_width = image_info.get("width", width)
    result_height = image_info.get("height", height)
    result_seed = data.get("seed", 0)

    image_bytes = None
    try:
        async with httpx.AsyncClient(timeout=60.0) as dl_client:
            dl_resp = await dl_client.get(remote_url)
            dl_resp.raise_for_status()
            image_bytes = dl_resp.content
    except Exception:
        logger.warning("Failed to download image from Fal.ai URL. URL will be used directly.")

    logger.info(
        "Fal.ai generation complete: %dx%d, seed=%d, size=%s bytes",
        result_width,
        result_height,
        result_seed,
        len(image_bytes) if image_bytes else "N/A",
    )

    return FalGenerationResult(
        image_url=remote_url,
        image_bytes=image_bytes,
        width=result_width,
        height=result_height,
        seed=result_seed,
        is_mock=False,
        model=FLUX_MODEL,
    )
