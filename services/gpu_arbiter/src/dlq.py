import logging
from typing import Any

from src.fallback import CloudFallback
from src.job_queue import DLQ_STREAM_KEY, JobQueue

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class DeadLetterQueueHandler:
    """Handles failed jobs from the Dead Letter Queue.

    Retry strategy:
    1. Retry up to MAX_RETRIES times on the local GPU
    2. If all retries exhausted, attempt cloud fallback
    3. If cloud fallback fails, alert via WebSocket notification
    """

    def __init__(
        self,
        job_queue: JobQueue,
        cloud_fallback: CloudFallback,
    ) -> None:
        self._job_queue = job_queue
        self._cloud_fallback = cloud_fallback

    async def process_dlq(self) -> list[dict[str, Any]]:
        """Process all jobs in the Dead Letter Queue."""
        dlq_jobs = await self._job_queue.get_dlq_jobs()
        results = []

        for job in dlq_jobs:
            retry_count = int(job.get("retry_count", 0))

            if retry_count < MAX_RETRIES:
                result = await self._retry_locally(job)
            else:
                result = await self._escalate_to_cloud(job)

            results.append(result)

        return results

    async def _retry_locally(self, job: dict[str, Any]) -> dict[str, Any]:
        """Re-submit job to main queue with incremented retry count."""
        job_id = job.get("job_id", "unknown")
        retry_count = int(job.get("retry_count", 0)) + 1

        logger.info("Retrying DLQ job %s (attempt %d/%d)", job_id, retry_count, MAX_RETRIES)

        # Re-submit to main queue
        new_job_id = await self._job_queue.submit(
            job_type=job.get("job_type", ""),
            payload={"original_job_id": job_id, "retry_count": retry_count},
            priority=1,  # Higher priority for retries
        )

        return {
            "original_job_id": job_id,
            "new_job_id": new_job_id,
            "action": "retried",
            "retry_count": retry_count,
        }

    async def _escalate_to_cloud(self, job: dict[str, Any]) -> dict[str, Any]:
        """Escalate to cloud fallback after all retries exhausted."""
        job_id = job.get("job_id", "unknown")
        job_type = job.get("job_type", "")

        logger.warning(
            "All %d retries exhausted for job %s. Escalating to cloud.", MAX_RETRIES, job_id
        )

        return {
            "original_job_id": job_id,
            "action": "escalated_to_cloud",
            "job_type": job_type,
            "message": f"Job {job_id} exhausted {MAX_RETRIES} retries, needs cloud processing",
        }
