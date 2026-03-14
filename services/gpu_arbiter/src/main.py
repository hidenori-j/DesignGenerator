import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from src.arbiter import GPUArbiter
from src.config import settings
from src.dlq import DeadLetterQueueHandler
from src.fallback import CloudFallback
from src.job_queue import JobQueue
from src.routes import health, jobs
from src.watchdog import GPUWatchdog

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_url = settings.redis_url

    job_queue = JobQueue(redis_url=redis_url)
    arbiter = GPUArbiter(redis_url=redis_url)
    cloud_fallback = CloudFallback(
        openai_api_key=settings.openai_api_key,
        fal_api_key=settings.fal_ai_api_key,
    )
    dlq_handler = DeadLetterQueueHandler(
        job_queue=job_queue,
        cloud_fallback=cloud_fallback,
    )
    watchdog = GPUWatchdog(redis_url=redis_url)

    try:
        await job_queue.initialize()
        logger.info("JobQueue initialized (Redis: %s)", redis_url)
    except Exception:
        logger.warning("Redis unavailable - GPU Arbiter running in degraded mode")

    watchdog_task = asyncio.create_task(watchdog.start())

    app.state.job_queue = job_queue
    app.state.arbiter = arbiter
    app.state.cloud_fallback = cloud_fallback
    app.state.dlq_handler = dlq_handler

    logger.info(
        "GPU Arbiter started: mode=%s, redis=%s",
        settings.gpu_mode,
        redis_url,
    )

    yield

    watchdog.stop()
    watchdog_task.cancel()
    await watchdog.close()
    await arbiter.close()
    await job_queue.close()
    logger.info("GPU Arbiter shutdown complete")


app = FastAPI(
    title="DesignGenerator GPU Arbiter",
    version="0.2.0",
    description="GPU Memory Arbiter: exclusive VRAM control, job scheduling, DLQ, cloud fallback",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(jobs.router, prefix="/api/v1")
