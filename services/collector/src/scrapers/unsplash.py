"""Unsplash scraper using their public API (license-friendly: Unsplash License)."""

import logging
from collections.abc import AsyncIterator

import httpx

from src.config import settings
from src.scrapers.base import BaseScraper, CollectedImage

logger = logging.getLogger(__name__)

UNSPLASH_API = "https://api.unsplash.com"


class UnsplashScraper(BaseScraper):
    """
    Uses the Unsplash API for image collection.
    Unsplash License allows free use for commercial/non-commercial purposes.
    """

    domain = "unsplash"

    def __init__(self, search_query: str = "web design", access_key: str = "", **kwargs):
        super().__init__(**kwargs)
        self.search_query = search_query
        self.access_key = access_key

    async def scrape(self) -> AsyncIterator[CollectedImage]:
        if not self.access_key:
            logger.warning("[unsplash] No access_key provided, skipping")
            return

        async with httpx.AsyncClient(
            headers={"Authorization": f"Client-ID {self.access_key}"},
            timeout=30.0,
        ) as client:
            for page_num in range(1, settings.max_pages + 1):
                resp = await client.get(
                    f"{UNSPLASH_API}/search/photos",
                    params={
                        "query": self.search_query,
                        "page": page_num,
                        "per_page": 30,
                        "orientation": "landscape",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])

                if not results:
                    break

                for photo in results:
                    try:
                        img_url = photo.get("urls", {}).get("regular", "")
                        if not img_url:
                            continue

                        filepath = await self.download_image(img_url)
                        if filepath is None:
                            continue

                        tags = [t["title"] for t in photo.get("tags", []) if "title" in t]

                        yield CollectedImage(
                            filepath=filepath,
                            source_url=img_url,
                            source_domain="unsplash.com",
                            page_url=photo.get("links", {}).get("html", ""),
                            title=photo.get("description") or photo.get("alt_description") or "",
                            tags=tags,
                            category="stock_photo",
                            license_type="unsplash_license",
                        )
                    except Exception:
                        logger.debug("[unsplash] Error processing photo", exc_info=True)
