import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum

import redis.asyncio as redis

logger = logging.getLogger(__name__)

STREAM_KEY = "gpu:jobs"
DLQ_STREAM_KEY = "gpu:dlq"
CONSUMER_GROUP = "gpu-workers"


class JobType(str, Enum):
    VLM_INFERENCE = "vlm_inference"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
    LORA_TRAINING = "lora_training"


JOB_TIMEOUTS: dict[str, int] = {
    JobType.VLM_INFERENCE: 120,
    JobType.EMBEDDING: 60,
    JobType.IMAGE_GENERATION: 300,
    JobType.LORA_TRAINING: 3600,
}


@dataclass
class GPUJob:
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_type: str = ""
    payload: str = "{}"
    priority: int = 0
    timeout_seconds: int = 300
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3


class JobQueue:
    """Redis Stream-based FIFO job queue for GPU tasks."""

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self._redis = redis.from_url(redis_url)

    async def initialize(self) -> None:
        """Create consumer group if it doesn't exist."""
        try:
            await self._redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
        except redis.ResponseError:
            pass  # Group already exists

    async def submit(self, job_type: str, payload: dict, priority: int = 0) -> str:
        """Submit a new GPU job to the queue."""
        job = GPUJob(
            job_type=job_type,
            payload=json.dumps(payload),
            priority=priority,
            timeout_seconds=JOB_TIMEOUTS.get(job_type, 300),
        )

        await self._redis.xadd(
            STREAM_KEY,
            {k: str(v) for k, v in asdict(job).items()},
        )

        logger.info("Job %s submitted: type=%s", job.job_id, job_type)
        return job.job_id

    async def move_to_dlq(self, job_data: dict, error: str) -> None:
        """Move a failed job to the Dead Letter Queue."""
        job_data["error"] = error
        job_data["failed_at"] = str(time.time())

        await self._redis.xadd(
            DLQ_STREAM_KEY,
            {k: str(v) for k, v in job_data.items()},
        )

        logger.warning("Job %s moved to DLQ: %s", job_data.get("job_id"), error)

    async def get_dlq_jobs(self, count: int = 50) -> list[dict]:
        """List jobs in the Dead Letter Queue."""
        entries = await self._redis.xrange(DLQ_STREAM_KEY, count=count)
        return [
            {"stream_id": entry_id, **{k.decode(): v.decode() for k, v in data.items()}}
            for entry_id, data in entries
        ]

    async def close(self) -> None:
        await self._redis.close()
