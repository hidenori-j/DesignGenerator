"""Generation endpoints: receives prompts from Agent, routes to providers, returns images."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.clients.fal_client import generate_with_fal
from src.clients.storage import upload_generated_image
from src.config import settings
from src.router.model_router import ModelProvider, ModelRouter, QueryRequirements

logger = logging.getLogger(__name__)

router = APIRouter()
model_router = ModelRouter()


class GenJobStatus(str, Enum):
    QUEUED = "queued"
    ROUTING = "routing"
    GENERATING = "generating"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationPromptRequest(BaseModel):
    """Matches the GenerationPrompt model from Agent service."""

    positive_prompt: str = ""
    negative_prompt: str = "blurry, low quality, distorted, watermark, text artifacts"
    style_prompt: str = ""
    reference_ids: list[str] = Field(default_factory=list)
    reference_mode: str = "hybrid"
    resolution: dict[str, int] = Field(
        default_factory=lambda: {"width": 1920, "height": 1080}
    )
    category: str = "unknown"
    color_palette: list[str] = Field(default_factory=list)
    layout_type: str = "freeform"
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenJobState(BaseModel):
    job_id: str
    status: GenJobStatus = GenJobStatus.QUEUED
    progress: int = 0
    image_url: str | None = None
    provider: str | None = None
    model_name: str | None = None
    routing_reason: str | None = None
    is_mock: bool = False
    error: str | None = None
    width: int = 0
    height: int = 0
    seed: int = 0
    created_at: str = ""
    finished_at: str | None = None


_jobs: dict[str, GenJobState] = {}


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str


@router.post("/generate")
async def generate(request: GenerationPromptRequest) -> GenerateResponse:
    job_id = str(uuid.uuid4())
    job = GenJobState(
        job_id=job_id,
        created_at=datetime.now(UTC).isoformat(),
    )
    _jobs[job_id] = job

    asyncio.create_task(_run_generation(job, request))

    return GenerateResponse(
        job_id=job_id,
        status="queued",
        message=f"Generation job queued: {request.positive_prompt[:80]}",
    )


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Generation job not found")
    return job.model_dump()


@router.get("/jobs")
async def list_jobs() -> list[dict[str, Any]]:
    return [
        {
            "job_id": j.job_id,
            "status": j.status,
            "progress": j.progress,
            "is_mock": j.is_mock,
            "provider": j.provider,
            "created_at": j.created_at,
            "finished_at": j.finished_at,
        }
        for j in _jobs.values()
    ]


async def _run_generation(job: GenJobState, request: GenerationPromptRequest) -> None:
    """Execute the generation pipeline in the background."""
    try:
        # Step 1: Route
        job.status = GenJobStatus.ROUTING
        job.progress = 10

        requirements = QueryRequirements.from_generation_prompt(request.model_dump())
        config = model_router.route(requirements)

        job.provider = config.provider.value
        job.model_name = config.model_name
        job.routing_reason = config.reason

        # Step 2: Generate
        job.status = GenJobStatus.GENERATING
        job.progress = 30

        width = request.resolution.get("width", 1920)
        height = request.resolution.get("height", 1080)

        if config.provider == ModelProvider.FAL_AI:
            result = await generate_with_fal(
                positive_prompt=request.positive_prompt,
                negative_prompt=request.negative_prompt,
                style_prompt=request.style_prompt,
                width=width,
                height=height,
                num_inference_steps=config.params.get("num_inference_steps", 28),
                guidance_scale=config.params.get("guidance_scale", 3.5),
            )
        else:
            logger.warning(
                "Provider %s not yet implemented (cloud-first phase). "
                "Falling back to Fal.ai.",
                config.provider,
            )
            result = await generate_with_fal(
                positive_prompt=request.positive_prompt,
                negative_prompt=request.negative_prompt,
                style_prompt=request.style_prompt,
                width=width,
                height=height,
            )

        job.progress = 70
        job.is_mock = result.is_mock
        job.width = result.width
        job.height = result.height
        job.seed = result.seed

        # Step 3: Upload to MinIO
        job.status = GenJobStatus.UPLOADING
        job.progress = 80

        if result.image_bytes and not result.is_mock:
            stored_url = await upload_generated_image(
                result.image_bytes,
                job_id=job.job_id,
            )
            job.image_url = stored_url if stored_url else result.image_url
        else:
            job.image_url = result.image_url

        # Done
        job.status = GenJobStatus.COMPLETED
        job.progress = 100
        logger.info(
            "Generation complete: job=%s, mock=%s, provider=%s, url=%s",
            job.job_id,
            job.is_mock,
            job.provider,
            job.image_url[:80] if job.image_url else "N/A",
        )

    except Exception as e:
        logger.error("Generation failed for job %s: %s", job.job_id, e, exc_info=True)
        job.status = GenJobStatus.FAILED
        job.error = str(e)
    finally:
        job.finished_at = datetime.now(UTC).isoformat()
