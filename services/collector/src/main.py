"""Collector FastAPI service for managing scraping/download jobs."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import settings
from src.ingest_client import push_to_ingest
from src.job_manager import create_job, get_job, list_jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DesignGenerator Collector", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateJobRequest(BaseModel):
    source: str
    query: str
    max_pages: int = 10
    max_images: int = 500
    auto_ingest: bool = False


class CreateJobResponse(BaseModel):
    job_id: str
    status: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": "collector"}


@app.post("/api/v1/jobs", response_model=CreateJobResponse)
async def start_job(req: CreateJobRequest):
    valid_sources = {"dribbble", "behance", "pinterest", "unsplash", "huggingface"}
    if req.source not in valid_sources:
        msg = f"Invalid source. Must be one of: {', '.join(sorted(valid_sources))}"
        raise HTTPException(400, msg)

    job = create_job(
        source=req.source,
        query=req.query,
        max_pages=req.max_pages,
        max_images=req.max_images,
        auto_ingest=req.auto_ingest,
    )
    return CreateJobResponse(job_id=job.job_id, status=job.status.value)


@app.get("/api/v1/jobs")
async def get_jobs() -> list[dict]:
    jobs = list_jobs()
    return [
        {
            "job_id": j.job_id,
            "status": j.status.value,
            "source": j.source,
            "query": j.query,
            "progress": j.progress,
            "total_collected": j.total_collected,
            "total_ingested": j.total_ingested,
            "created_at": j.created_at,
            "finished_at": j.finished_at,
        }
        for j in jobs
    ]


@app.get("/api/v1/jobs/{job_id}")
async def get_job_detail(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "source": job.source,
        "query": job.query,
        "progress": job.progress,
        "total_collected": job.total_collected,
        "total_ingested": job.total_ingested,
        "auto_ingest": job.auto_ingest,
        "max_pages": job.max_pages,
        "max_images": job.max_images,
        "error": job.error,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


@app.get("/api/v1/jobs/{job_id}/images")
async def get_job_images(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.job_id,
        "total": len(job.images),
        "images": [img.model_dump() for img in job.images],
    }
