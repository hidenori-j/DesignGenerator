import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis

logger = logging.getLogger(__name__)

GPU_SEMAPHORE_KEY = "gpu:semaphore"
GPU_LOCK_TTL = 600  # Max 10 minutes per job


class GPUArbiter:
    """Semaphore-based exclusive GPU control using Redis.

    Ensures only one GPU-intensive process (VLM inference OR image generation)
    runs at a time on the local RTX 5080 (16GB VRAM).
    """

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self._redis = redis.from_url(redis_url)
        self._poll_interval = 0.5

    @asynccontextmanager
    async def acquire_gpu(
        self,
        job_id: str,
        job_type: str,
        timeout_seconds: int = 300,
    ) -> AsyncGenerator[None, None]:
        """Acquire exclusive GPU access. Blocks until GPU is available or timeout."""
        deadline = time.monotonic() + timeout_seconds
        acquired = False

        try:
            while time.monotonic() < deadline:
                acquired = await self._redis.set(
                    GPU_SEMAPHORE_KEY,
                    f"{job_id}:{job_type}:{int(time.time())}",
                    nx=True,
                    ex=GPU_LOCK_TTL,
                )
                if acquired:
                    logger.info("GPU acquired for job %s (%s)", job_id, job_type)
                    break
                await asyncio.sleep(self._poll_interval)

            if not acquired:
                raise TimeoutError(
                    f"Failed to acquire GPU within {timeout_seconds}s for job {job_id}"
                )

            yield

        finally:
            if acquired:
                await self._release_gpu(job_id)

    async def _release_gpu(self, job_id: str) -> None:
        """Release GPU semaphore, verifying ownership."""
        current = await self._redis.get(GPU_SEMAPHORE_KEY)
        if current and current.decode().startswith(job_id):
            await self._redis.delete(GPU_SEMAPHORE_KEY)
            logger.info("GPU released by job %s", job_id)

    async def force_release(self) -> None:
        """Force-release the GPU semaphore (used by watchdog on crash recovery)."""
        await self._redis.delete(GPU_SEMAPHORE_KEY)
        logger.warning("GPU semaphore force-released by watchdog")

    async def get_status(self) -> dict[str, str | None]:
        """Get current GPU semaphore status."""
        current = await self._redis.get(GPU_SEMAPHORE_KEY)
        if current:
            parts = current.decode().split(":")
            return {
                "locked": "true",
                "job_id": parts[0] if len(parts) > 0 else None,
                "job_type": parts[1] if len(parts) > 1 else None,
                "locked_at": parts[2] if len(parts) > 2 else None,
            }
        return {"locked": "false", "job_id": None, "job_type": None, "locked_at": None}

    async def close(self) -> None:
        await self._redis.close()
