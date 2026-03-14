"""In-memory job manager for collector scraping/download tasks."""

import asyncio
import concurrent.futures
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.config import settings
from src.ingest_client import push_to_ingest
from src.scrapers.base import CollectedImage

logger = logging.getLogger(__name__)

_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CollectedImageInfo(BaseModel):
    filename: str
    source_url: str
    source_domain: str
    title: str = ""
    category: str = "unknown"
    license_type: str = "copyrighted_reference"
    ingested: bool = False


class JobState(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    source: str
    query: str
    max_pages: int = 10
    max_images: int = 500
    auto_ingest: bool = False
    progress: int = 0
    total_collected: int = 0
    total_ingested: int = 0
    error: str | None = None
    images: list[CollectedImageInfo] = Field(default_factory=list)
    created_at: str = ""
    finished_at: str | None = None


_jobs: dict[str, JobState] = {}
_tasks: dict[str, asyncio.Task] = {}


def create_job(
    source: str,
    query: str,
    max_pages: int = 10,
    max_images: int = 500,
    auto_ingest: bool = False,
) -> JobState:
    job_id = str(uuid.uuid4())
    job = JobState(
        job_id=job_id,
        source=source,
        query=query,
        max_pages=max_pages,
        max_images=max_images,
        auto_ingest=auto_ingest,
        created_at=datetime.now(UTC).isoformat(),
    )
    _jobs[job_id] = job
    task = asyncio.create_task(_run_job(job))
    _tasks[job_id] = task
    return job


def get_job(job_id: str) -> JobState | None:
    return _jobs.get(job_id)


def list_jobs() -> list[JobState]:
    return list(_jobs.values())


def _get_scraper(source: str, query: str):
    from src.scrapers.behance import BehanceScraper
    from src.scrapers.dribbble import DribbbleScraper
    from src.scrapers.pinterest import PinterestScraper
    from src.scrapers.unsplash import UnsplashScraper

    scrapers = {
        "dribbble": lambda: DribbbleScraper(search_query=query),
        "behance": lambda: BehanceScraper(search_query=query),
        "pinterest": lambda: PinterestScraper(search_query=query),
        "unsplash": lambda: UnsplashScraper(
            search_query=query,
            access_key=os.environ.get("UNSPLASH_ACCESS_KEY", ""),
        ),
    }
    factory = scrapers.get(source)
    return factory() if factory else None


def _run_scraper_in_thread(job: JobState) -> list[CollectedImage]:
    """
    Run Playwright scraper in a dedicated thread with its own ProactorEventLoop.
    Windows SelectorEventLoop (used by uvicorn) doesn't support subprocesses,
    so Playwright must run on a ProactorEventLoop in a separate thread.
    """
    loop = asyncio.new_event_loop()
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()

    try:
        return loop.run_until_complete(_scrape_async(job, loop))
    finally:
        loop.close()


async def _scrape_async(job: JobState, _loop: asyncio.AbstractEventLoop) -> list[CollectedImage]:
    scraper = _get_scraper(job.source, job.query)
    if scraper is None:
        msg = f"Unknown source: {job.source}"
        raise ValueError(msg)

    settings.max_pages = job.max_pages
    settings.max_images_per_source = job.max_images

    collected: list[CollectedImage] = []
    count = 0
    async for item in scraper.scrape():
        collected.append(item)
        count += 1
        job.total_collected = count
        job.progress = min(95, int(count / max(job.max_images, 1) * 100))

        job.images.append(
            CollectedImageInfo(
                filename=item.filepath.name,
                source_url=item.source_url,
                source_domain=item.source_domain,
                title=item.title,
                category=item.category,
                license_type=item.license_type,
            )
        )

        if count >= job.max_images:
            break
        await asyncio.sleep(settings.request_delay)

    return collected


async def _run_job(job: JobState) -> None:
    job.status = JobStatus.RUNNING
    try:
        if job.source == "huggingface":
            await _run_hf_job(job)
        else:
            main_loop = asyncio.get_running_loop()
            collected = await main_loop.run_in_executor(
                _thread_pool, _run_scraper_in_thread, job
            )
            if job.auto_ingest:
                await _ingest_collected(job, collected)
            job.progress = 100

        job.status = JobStatus.COMPLETED
    except Exception as e:
        logger.error("Job %s failed: %s", job.job_id, e, exc_info=True)
        job.status = JobStatus.FAILED
        job.error = str(e)
    finally:
        job.finished_at = datetime.now(UTC).isoformat()


async def _run_hf_job(job: JobState) -> None:
    from src.datasets.hf_loader import load_hf_dataset

    results = await load_hf_dataset(
        job.query,
        category="design_reference",
        max_samples=job.max_images,
    )

    for item in results:
        job.total_collected += 1
        job.progress = min(95, int(job.total_collected / max(job.max_images, 1) * 100))
        job.images.append(
            CollectedImageInfo(
                filename=item.filepath.name,
                source_url=item.source_url,
                source_domain=item.source_domain,
                title=item.title,
                category=item.category,
                license_type=item.license_type,
            )
        )

    if job.auto_ingest:
        await _ingest_collected(job, results)

    job.progress = 100


async def _ingest_collected(job: JobState, items: list[CollectedImage]) -> None:
    for i, item in enumerate(items):
        try:
            await push_to_ingest(
                item.filepath,
                category=item.category,
                license_type=item.license_type,
                source_url=item.source_url,
                source_domain=item.source_domain,
            )
            job.total_ingested += 1
            if i < len(job.images):
                job.images[i].ingested = True
        except Exception:
            logger.warning("Failed to ingest %s", item.filepath.name, exc_info=True)
