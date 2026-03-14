"""Behance gallery scraper using Playwright."""

import logging
from collections.abc import AsyncIterator

from playwright.async_api import async_playwright

from src.config import settings
from src.scrapers.base import BaseScraper, CollectedImage

logger = logging.getLogger(__name__)


class BehanceScraper(BaseScraper):
    domain = "behance"

    def __init__(self, search_query: str = "web design ui", **kwargs):
        super().__init__(**kwargs)
        self.search_query = search_query

    async def scrape(self) -> AsyncIterator[CollectedImage]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            for page_num in range(1, settings.max_pages + 1):
                url = (
                    f"https://www.behance.net/search/projects"
                    f"?search={self.search_query}&page={page_num}"
                )
                logger.info("[behance] Loading page %d: %s", page_num, url)
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30_000)
                except Exception:
                    logger.warning("[behance] Page load timeout, continuing")

                cards = page.locator("div.ProjectCoverNeue-root-166")
                count = await cards.count()
                if count == 0:
                    # Behance updates class names frequently; fallback
                    cards = page.locator("img[src*='project_modules']")
                    count = await cards.count()

                if count == 0:
                    logger.info("[behance] No results at page %d", page_num)
                    break

                for i in range(count):
                    try:
                        img_el = cards.nth(i) if "img" in await cards.nth(i).evaluate(
                            "el => el.tagName"
                        ) else cards.nth(i).locator("img").first
                        src = await img_el.get_attribute("src") or ""
                        alt = await img_el.get_attribute("alt") or ""

                        if not src or "gif" in src:
                            continue

                        # Request higher resolution
                        high_res = src.split("?")[0]

                        filepath = await self.download_image(high_res)
                        if filepath is None:
                            continue

                        yield CollectedImage(
                            filepath=filepath,
                            source_url=high_res,
                            source_domain="behance.net",
                            page_url=url,
                            title=alt,
                            tags=self.search_query.split(),
                            category="web_design",
                            license_type="copyrighted_reference",
                        )
                    except Exception:
                        logger.debug("[behance] Error processing card %d", i, exc_info=True)

            await browser.close()
