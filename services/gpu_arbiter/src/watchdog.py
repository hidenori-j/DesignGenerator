import asyncio
import logging
import time

import redis.asyncio as redis

from src.arbiter import GPU_LOCK_TTL, GPU_SEMAPHORE_KEY

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL = 10  # Check every 10 seconds
STALE_THRESHOLD = GPU_LOCK_TTL * 0.8  # Consider stale at 80% of TTL


class GPUWatchdog:
    """Monitors GPU semaphore health and force-releases on crash/hang.

    Prevents deadlock when a process holding the GPU semaphore crashes
    without releasing it. Also monitors for jobs that exceed their timeout.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self._redis = redis.from_url(redis_url)
        self._running = False

    async def start(self) -> None:
        """Start the watchdog loop."""
        self._running = True
        logger.info("GPU Watchdog started (interval=%ds)", WATCHDOG_INTERVAL)

        while self._running:
            try:
                await self._check_semaphore()
            except Exception:
                logger.exception("Watchdog check failed")

            await asyncio.sleep(WATCHDOG_INTERVAL)

    async def _check_semaphore(self) -> None:
        """Check if the GPU semaphore is stale (holder likely crashed)."""
        current = await self._redis.get(GPU_SEMAPHORE_KEY)
        if not current:
            return

        parts = current.decode().split(":")
        if len(parts) < 3:
            return

        locked_at = float(parts[2])
        elapsed = time.time() - locked_at

        if elapsed > STALE_THRESHOLD:
            logger.warning(
                "Stale GPU lock detected: job=%s, type=%s, held for %.0fs. Force-releasing.",
                parts[0],
                parts[1],
                elapsed,
            )
            await self._redis.delete(GPU_SEMAPHORE_KEY)

    def stop(self) -> None:
        self._running = False

    async def close(self) -> None:
        self.stop()
        await self._redis.close()
