import logging
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class FallbackTarget(str, Enum):
    GPT54_VISION = "gpt54_vision"
    FAL_AI_FLUX = "fal_ai_flux"


class CloudFallback:
    """Routes GPU tasks to cloud APIs when local GPU is unavailable.

    Fallback strategies:
    - VLM inference -> GPT-5.4 Vision API (metadata extraction)
    - Image generation -> Fal.ai FLUX.2 Pro API
    """

    def __init__(
        self,
        openai_api_key: str = "",
        fal_api_key: str = "",
    ) -> None:
        self._openai_key = openai_api_key
        self._fal_key = fal_api_key

    async def should_fallback(self, gpu_mode: str, gpu_available: bool) -> bool:
        """Determine if cloud fallback should be used."""
        if gpu_mode == "cloud":
            return True
        if gpu_mode == "hybrid" and not gpu_available:
            return True
        return False

    async def fallback_vlm_inference(
        self,
        image_url: str,
        extraction_prompt: str,
    ) -> dict[str, str]:
        """Fall back to GPT-5.4 Vision for VLM inference."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._openai_key}"},
                json={
                    "model": "gpt-5.4",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": extraction_prompt},
                                {"type": "image_url", "image_url": {"url": image_url}},
                            ],
                        }
                    ],
                    "max_tokens": 2000,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        logger.info("VLM fallback to GPT-5.4 Vision completed")
        return {"source": "gpt-5.4-vision", "content": content}

    async def fallback_image_generation(
        self,
        prompt: str,
        reference_images: list[str] | None = None,
    ) -> dict[str, str]:
        """Fall back to Fal.ai FLUX.2 Pro for image generation."""
        async with httpx.AsyncClient() as client:
            payload: dict = {
                "prompt": prompt,
                "num_inference_steps": 28,
                "guidance_scale": 3.5,
            }
            if reference_images:
                payload["image_url"] = reference_images[0]

            response = await client.post(
                "https://fal.run/fal-ai/flux-pro/v1.1",
                headers={"Authorization": f"Key {self._fal_key}"},
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

        logger.info("Generation fallback to Fal.ai FLUX.2 Pro completed")
        return {"source": "fal-ai-flux-pro", "image_url": data.get("images", [{}])[0].get("url", "")}
