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


# ---------------------------------------------------------------------------
# Local file management: list & bulk ingest
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@app.get("/api/v1/local/files")
async def list_local_files(source: str | None = None) -> dict:
    """List downloaded image files on disk, optionally filtered by source."""
    base = settings.download_dir
    if not base.exists():
        return {"total": 0, "sources": {}, "files": []}

    if source:
        dirs = [base / source] if (base / source).is_dir() else []
    else:
        dirs = [d for d in sorted(base.iterdir()) if d.is_dir()]

    files: list[dict] = []
    sources_summary: dict[str, int] = {}
    for d in dirs:
        count = 0
        for f in sorted(d.iterdir()):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                files.append({
                    "filename": f.name,
                    "source": d.name,
                    "size": f.stat().st_size,
                    "path": str(f),
                })
                count += 1
        if count > 0:
            sources_summary[d.name] = count

    return {"total": len(files), "sources": sources_summary, "files": files}


class BulkIngestRequest(BaseModel):
    source: str | None = None
    category: str = "unknown"
    dedup: str = "skip"


_bulk_jobs: dict[str, dict] = {}


@app.post("/api/v1/local/ingest")
async def bulk_ingest_local(req: BulkIngestRequest) -> dict:
    """Start a bulk ingest job for locally downloaded files."""
    base = settings.download_dir
    if not base.exists():
        raise HTTPException(400, f"Download directory does not exist: {base}")

    if req.source:
        dirs = [base / req.source] if (base / req.source).is_dir() else []
    else:
        dirs = [d for d in base.iterdir() if d.is_dir()]

    file_paths = []
    for d in dirs:
        for f in sorted(d.iterdir()):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                file_paths.append((f, d.name))

    if not file_paths:
        raise HTTPException(400, "No image files found in the specified directory")

    job_id = str(uuid.uuid4())
    job_state = {
        "job_id": job_id,
        "status": "running",
        "total": len(file_paths),
        "ingested": 0,
        "skipped": 0,
        "failed": 0,
        "progress": 0,
        "category": req.category,
        "dedup": req.dedup,
        "source": req.source or "all",
        "errors": [],
        "created_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
    }
    _bulk_jobs[job_id] = job_state
    asyncio.create_task(_run_bulk_ingest(job_state, file_paths, req.category, req.dedup))
    return {"job_id": job_id, "status": "running", "total": len(file_paths)}


@app.get("/api/v1/local/ingest/{job_id}")
async def get_bulk_ingest_status(job_id: str) -> dict:
    """Get status of a bulk ingest job."""
    job = _bulk_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Bulk ingest job not found")
    return job


async def _run_bulk_ingest(
    job: dict,
    file_paths: list[tuple],
    category: str,
    dedup: str,
) -> None:
    for i, (filepath, source_name) in enumerate(file_paths):
        try:
            await push_to_ingest(
                filepath,
                category=category,
                license_type="copyrighted_reference",
                source_url="",
                source_domain=source_name,
                dedup=dedup,
            )
            job["ingested"] += 1
        except Exception as e:
            err_msg = str(e)
            if "Duplicate skipped" in err_msg or "skipped" in err_msg.lower():
                job["skipped"] += 1
            else:
                job["failed"] += 1
                if len(job["errors"]) < 20:
                    job["errors"].append({"file": filepath.name, "error": err_msg})
                logger.warning("Bulk ingest failed for %s: %s", filepath.name, e)
        job["progress"] = int((i + 1) / job["total"] * 100)

    job["status"] = "completed"
    job["finished_at"] = datetime.now(UTC).isoformat()
    logger.info(
        "Bulk ingest completed: %d ingested, %d skipped, %d failed",
        job["ingested"], job["skipped"], job["failed"],
    )
