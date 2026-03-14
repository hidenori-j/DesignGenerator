"""Design generation endpoint with LangGraph RAG pipeline + Generation Service call."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config import settings
from src.rag.graph import run_rag_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()

GENERATION_POLL_INTERVAL = 1.5
GENERATION_POLL_TIMEOUT = 300


class JobStatus(str, Enum):
    QUEUED = "queued"
    DECOMPOSING = "decomposing"
    SEARCHING = "searching"
    RERANKING = "reranking"
    BUILDING_PROMPT = "building_prompt"
    GENERATING = "generating"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


class JobState(BaseModel):
    job_id: str
    status: str = "queued"
    progress: int = 0
    prompt: str = ""
    error: str | None = None
    generation_prompt: dict | None = None
    references_found: int = 0
    image_url: str | None = None
    is_mock: bool = False
    provider: str | None = None
    created_at: str = ""
    finished_at: str | None = None


_jobs: dict[str, JobState] = {}


class GenerateRequest(BaseModel):
    prompt: str
    style_reference_ids: list[str] = Field(default_factory=list)
    layout_reference_ids: list[str] = Field(default_factory=list)
    brand: str | None = None
    resolution: dict[str, int] | None = None
    reference_mode: Literal["style_only", "layout_only", "hybrid"] = "hybrid"


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str


@router.post("/generate")
async def generate_design(request: GenerateRequest) -> GenerateResponse:
    job_id = str(uuid.uuid4())
    job = JobState(
        job_id=job_id,
        prompt=request.prompt,
        created_at=datetime.now(UTC).isoformat(),
    )
    _jobs[job_id] = job

    asyncio.create_task(_run_pipeline(job, request))

    return GenerateResponse(
        job_id=job_id,
        status="queued",
        message=f"Generation job queued: {request.prompt[:100]}",
    )


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job.model_dump()


@router.get("/jobs")
async def list_jobs() -> list[dict[str, Any]]:
    return [
        {
            "job_id": j.job_id,
            "status": j.status,
            "progress": j.progress,
            "prompt": j.prompt[:80],
            "references_found": j.references_found,
            "image_url": j.image_url,
            "is_mock": j.is_mock,
            "created_at": j.created_at,
            "finished_at": j.finished_at,
        }
        for j in _jobs.values()
    ]


async def _run_pipeline(job: JobState, request: GenerateRequest) -> None:
    """Execute the RAG pipeline then call Generation Service."""
    try:
        # --- Phase 1: RAG Pipeline ---
        job.status = JobStatus.DECOMPOSING
        job.progress = 10

        result = await run_rag_pipeline(
            prompt=request.prompt,
            brand=request.brand,
            reference_mode=request.reference_mode,
            resolution=request.resolution,
            style_reference_ids=request.style_reference_ids,
            layout_reference_ids=request.layout_reference_ids,
        )

        if result.get("error"):
            job.status = JobStatus.FAILED
            job.error = result["error"]
            job.progress = 0
            return

        job.progress = 30
        job.status = JobStatus.SEARCHING

        ranked = result.get("ranked_results", [])
        job.references_found = len(ranked)
        job.progress = 45
        job.status = JobStatus.RERANKING

        gen_prompt = result.get("generation_prompt")
        if gen_prompt:
            job.generation_prompt = gen_prompt.model_dump()

        job.progress = 55
        job.status = JobStatus.BUILDING_PROMPT

        # --- Phase 2: Call Generation Service ---
        if not job.generation_prompt:
            job.status = JobStatus.FAILED
            job.error = "RAG pipeline produced no generation prompt"
            return

        job.status = JobStatus.GENERATING
        job.progress = 60

        gen_result = await _call_generation_service(job.generation_prompt)

        if gen_result.get("error"):
            job.status = JobStatus.FAILED
            job.error = gen_result["error"]
            return

        job.image_url = gen_result.get("image_url")
        job.is_mock = gen_result.get("is_mock", False)
        job.provider = gen_result.get("provider")
        job.progress = 100
        job.status = JobStatus.COMPLETED

        logger.info(
            "Pipeline complete: job=%s, mock=%s, provider=%s",
            job.job_id,
            job.is_mock,
            job.provider,
        )

    except Exception as e:
        logger.error("Pipeline failed for job %s: %s", job.job_id, e, exc_info=True)
        job.status = JobStatus.FAILED
        job.error = str(e)
    finally:
        job.finished_at = datetime.now(UTC).isoformat()


async def _call_generation_service(generation_prompt: dict[str, Any]) -> dict[str, Any]:
    """Submit generation prompt to Generation Service and poll until complete."""
    gen_url = settings.generation_service_url

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{gen_url}/api/v1/generate",
                json=generation_prompt,
            )
            resp.raise_for_status()
            submit_data = resp.json()
        except httpx.ConnectError:
            logger.warning(
                "Generation Service unavailable at %s. Returning mock result.", gen_url
            )
            return {
                "image_url": "https://placehold.co/1920x1080/1a1a2e/eee"
                "?text=Generation+Service+Offline&font=noto-sans-jp",
                "is_mock": True,
                "provider": "mock",
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Generation Service returned {e.response.status_code}"}

    gen_job_id = submit_data.get("job_id", "")
    if not gen_job_id:
        return {"error": "Generation Service returned no job_id"}

    elapsed = 0.0
    async with httpx.AsyncClient(timeout=15.0) as client:
        while elapsed < GENERATION_POLL_TIMEOUT:
            await asyncio.sleep(GENERATION_POLL_INTERVAL)
            elapsed += GENERATION_POLL_INTERVAL

            try:
                status_resp = await client.get(f"{gen_url}/api/v1/jobs/{gen_job_id}")
                status_resp.raise_for_status()
                status_data = status_resp.json()
            except Exception:
                logger.warning("Failed to poll Generation Service job %s", gen_job_id)
                continue

            gen_status = status_data.get("status", "")

            if gen_status == "completed":
                return {
                    "image_url": status_data.get("image_url"),
                    "is_mock": status_data.get("is_mock", False),
                    "provider": status_data.get("provider"),
                }
            elif gen_status == "failed":
                return {"error": status_data.get("error", "Generation failed")}

    return {"error": f"Generation timed out after {GENERATION_POLL_TIMEOUT}s"}
