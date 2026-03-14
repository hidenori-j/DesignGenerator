"""Model routing: selects the optimal generation provider based on requirements and GPU mode."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


class ModelProvider(str, Enum):
    LOCAL_COMFYUI = "local_comfyui"
    FAL_AI = "fal_ai"
    ADOBE_FIREFLY = "adobe_firefly"
    RECRAFT = "recraft"


@dataclass
class GenerationConfig:
    provider: ModelProvider
    model_name: str
    params: dict[str, Any]
    reason: str


@dataclass
class QueryRequirements:
    requires_photorealism: bool = False
    requires_typography: bool = False
    requires_vector_output: bool = False
    requires_commercial_safe: bool = False
    requires_low_latency: bool = False

    @classmethod
    def from_generation_prompt(cls, prompt_data: dict[str, Any]) -> QueryRequirements:
        """Infer requirements from a GenerationPrompt dict (from Agent service)."""
        category = prompt_data.get("category", "").lower()
        metadata = prompt_data.get("metadata", {})
        style = prompt_data.get("style_prompt", "").lower()
        positive = prompt_data.get("positive_prompt", "").lower()

        photorealism_keywords = {"photo", "realistic", "photography", "photograph", "cinematic"}
        typography_keywords = {"typography", "text", "ui", "interface", "dashboard", "app"}
        vector_keywords = {"vector", "illustration", "icon", "logo", "flat"}
        commercial_keywords = {"commercial", "stock", "licensed", "brand-safe"}

        return cls(
            requires_photorealism=bool(
                photorealism_keywords & set(positive.split())
                or photorealism_keywords & set(style.split())
            ),
            requires_typography=bool(
                category in ("ui", "dashboard", "app", "web")
                or typography_keywords & set(positive.split())
                or metadata.get("requires_typography", False)
            ),
            requires_vector_output=bool(
                category in ("icon", "logo", "illustration")
                or vector_keywords & set(positive.split())
            ),
            requires_commercial_safe=bool(
                metadata.get("commercial_safe", False)
                or commercial_keywords & set(positive.split())
            ),
            requires_low_latency=bool(metadata.get("low_latency", False)),
        )


class ModelRouter:
    """Routes generation requests to the optimal model based on requirements."""

    def route(self, requirements: QueryRequirements) -> GenerationConfig:
        config = self._select_by_requirements(requirements)

        if settings.gpu_mode == "cloud" and config.provider == ModelProvider.LOCAL_COMFYUI:
            config = self._reroute_to_cloud(config)

        logger.info("ModelRouter: %s → %s (%s)", config.model_name, config.provider, config.reason)
        return config

    def _select_by_requirements(self, requirements: QueryRequirements) -> GenerationConfig:
        if requirements.requires_commercial_safe:
            return self._route_to_firefly()
        if requirements.requires_photorealism:
            return self._route_to_flux_pro()
        if requirements.requires_typography:
            return self._route_to_glm_image()
        if requirements.requires_vector_output:
            return self._route_to_recraft_v3()
        return self._route_to_local_flux()

    def _reroute_to_cloud(self, original: GenerationConfig) -> GenerationConfig:
        """When GPU_MODE=cloud, redirect local routes to Fal.ai."""
        logger.info(
            "GPU_MODE=cloud: rerouting %s (%s) → Fal.ai FLUX.2 Pro",
            original.model_name,
            original.provider,
        )
        return GenerationConfig(
            provider=ModelProvider.FAL_AI,
            model_name="fal-ai/flux-pro/v1.1",
            params={
                **original.params,
                "num_inference_steps": original.params.get("num_inference_steps", 28),
                "guidance_scale": original.params.get("guidance_scale", 3.5),
            },
            reason=f"Cloud reroute: {original.reason}",
        )

    def _route_to_flux_pro(self) -> GenerationConfig:
        return GenerationConfig(
            provider=ModelProvider.FAL_AI,
            model_name="fal-ai/flux-pro/v1.1",
            params={"num_inference_steps": 28, "guidance_scale": 3.5},
            reason="Photorealistic output required - routing to FLUX.2 Pro via Fal.ai",
        )

    def _route_to_glm_image(self) -> GenerationConfig:
        return GenerationConfig(
            provider=ModelProvider.LOCAL_COMFYUI,
            model_name="glm-image-9b",
            params={"num_inference_steps": 30},
            reason="Typography/UI generation required - routing to GLM-Image (local)",
        )

    def _route_to_recraft_v3(self) -> GenerationConfig:
        return GenerationConfig(
            provider=ModelProvider.RECRAFT,
            model_name="recraft-v3",
            params={"style": "vector_illustration"},
            reason="Vector output required - routing to Recraft V3",
        )

    def _route_to_firefly(self) -> GenerationConfig:
        return GenerationConfig(
            provider=ModelProvider.ADOBE_FIREFLY,
            model_name="firefly-image-3",
            params={},
            reason="Commercial safety required - routing to Adobe Firefly 3",
        )

    def _route_to_local_flux(self) -> GenerationConfig:
        return GenerationConfig(
            provider=ModelProvider.LOCAL_COMFYUI,
            model_name="flux-1-dev",
            params={"num_inference_steps": 20, "guidance_scale": 3.5},
            reason="Standard generation - routing to local FLUX.1-dev via ComfyUI",
        )
