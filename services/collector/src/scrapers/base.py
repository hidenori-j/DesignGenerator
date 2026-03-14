"""Abstract base for gallery scrapers."""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
from pydantic import BaseModel

from src.config import settings

logger = logging.getLogger(__name__)


class CollectedImage(BaseModel):
    """Metadata for a downloaded image."""

    filepath: Path
    source_url: str
    source_domain: str
    page_url: str
    title: str = ""
    tags: list[str] = []
    category: str = "unknown"
    license_type: str = "copyrighted_reference"


class BaseScraper(ABC):
    """
    Provides common download/dedup logic.
    Subclasses implement `scrape()` to yield image URLs from specific gallery sites.
    """

    domain: str = ""

    def __init__(self, download_dir: Path | None = None, headless: bool | None = None):
        self.download_dir = download_dir or settings.download_dir / self.domain
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless if headless is not None else settings.headless
        self._seen_hashes: set[str] = set()
        self._load_existing_hashes()

    def _load_existing_hashes(self) -> None:
        """Build dedup set from already-downloaded files."""
        for f in self.download_dir.glob("*"):
            if f.is_file():
                h = hashlib.sha256(f.read_bytes()).hexdigest()
                self._seen_hashes.add(h)
        logger.info("[%s] Loaded %d existing file hashes", self.domain, len(self._seen_hashes))

    def _is_duplicate(self, data: bytes) -> bool:
        h = hashlib.sha256(data).hexdigest()
        if h in self._seen_hashes:
            return True
        self._seen_hashes.add(h)
        return False

    async def download_image(self, url: str, *, filename: str | None = None) -> Path | None:
        """Download an image if it's not a duplicate. Returns local path or None."""
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={"User-Agent": "DesignGenerator-Collector/0.1 (research)"},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.content

            if len(data) < 5_000:
                logger.debug("Skipping tiny image (%d bytes): %s", len(data), url)
                return None

            if self._is_duplicate(data):
                logger.debug("Duplicate skipped: %s", url)
                return None

            if filename is None:
                ext = url.rsplit(".", 1)[-1].split("?")[0][:4]
                if ext.lower() not in ("jpg", "jpeg", "png", "webp"):
                    ext = "jpg"
                h = hashlib.sha256(data).hexdigest()[:16]
                filename = f"{h}.{ext}"

            filepath = self.download_dir / filename
            filepath.write_bytes(data)
            logger.info("Downloaded: %s", filepath.name)
            return filepath
        except Exception:
            logger.warning("Failed to download: %s", url, exc_info=True)
            return None

    @abstractmethod
    async def scrape(self) -> AsyncIterator[CollectedImage]:
        """Yield CollectedImage items from the gallery site."""
        ...  # pragma: no cover

    async def run(self) -> list[CollectedImage]:
        """Execute scraping and return all collected images."""
        results: list[CollectedImage] = []
        count = 0
        async for item in self.scrape():
            results.append(item)
            count += 1
            if count >= settings.max_images_per_source:
                logger.info("[%s] Reached max_images_per_source=%d", self.domain, count)
                break
            await asyncio.sleep(settings.request_delay)
        logger.info("[%s] Collected %d images total", self.domain, len(results))
        return results
