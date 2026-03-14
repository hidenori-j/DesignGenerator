"""GPU Arbiter job management routes - wired to JobQueue, Arbiter, and DLQ."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class JobType(str, Enum):
    VLM_INFERENCE = "vlm_inference"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
    LORA_TRAINING = "lora_training"


class JobStatus(str, Enum):
    QUEUED = "queued"
    ACQUIRING_GPU = "acquiring_gpu"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


class SubmitJobRequest(BaseModel):
    job_type: JobType
    payload: dict[str, Any]
    priority: int = 0
    timeout_seconds: int | None = None


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


@router.post("/jobs/submit")
async def submit_job(request_body: SubmitJobRequest, request: Request) -> JobResponse:
    job_queue = request.app.state.job_queue

    try:
        job_id = await job_queue.submit(
            job_type=request_body.job_type.value,
            payload=request_body.payload,
            priority=request_body.priority,
        )
    except Exception as e:
        logger.error("Failed to submit job: %s", e)
        raise HTTPException(503, "Redis unavailable - cannot submit job") from e

    return JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message=f"Job of type {request_body.job_type} queued",
    )


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> JobResponse:
    return JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message="Per-job status tracking will be available with Redis consumer workers",
    )


@router.get("/jobs/dlq/list")
async def list_dead_letter_queue(request: Request) -> dict[str, Any]:
    job_queue = request.app.state.job_queue

    try:
        jobs = await job_queue.get_dlq_jobs()
    except Exception:
        logger.warning("Failed to read DLQ from Redis")
        jobs = []

    return {"jobs": jobs, "count": len(jobs)}


@router.post("/jobs/dlq/process")
async def process_dlq(request: Request) -> dict[str, Any]:
    dlq_handler = request.app.state.dlq_handler

    try:
        results = await dlq_handler.process_dlq()
    except Exception as e:
        logger.error("DLQ processing failed: %s", e)
        raise HTTPException(500, "DLQ processing failed") from e

    return {"processed": len(results), "results": results}


@router.get("/gpu/status")
async def gpu_status(request: Request) -> dict[str, Any]:
    arbiter = request.app.state.arbiter

    try:
        status = await arbiter.get_status()
    except Exception:
        logger.warning("Failed to get GPU status from Redis")
        status = {"locked": "unknown", "error": "Redis unavailable"}

    return status


@router.post("/gpu/force-release")
async def force_release_gpu(request: Request) -> dict[str, str]:
    arbiter = request.app.state.arbiter

    try:
        await arbiter.force_release()
    except Exception as e:
        raise HTTPException(500, f"Force release failed: {e}") from e

    return {"status": "released", "message": "GPU semaphore force-released"}
