"""Pinterest gallery scraper using Playwright."""

import logging
from collections.abc import AsyncIterator

from playwright.async_api import async_playwright

from src.config import settings
from src.scrapers.base import BaseScraper, CollectedImage

logger = logging.getLogger(__name__)


class PinterestScraper(BaseScraper):
    domain = "pinterest"

    def __init__(self, search_query: str = "web design inspiration", **kwargs):
        super().__init__(**kwargs)
        self.search_query = search_query

    async def scrape(self) -> AsyncIterator[CollectedImage]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            url = f"https://www.pinterest.com/search/pins/?q={self.search_query}"
            logger.info("[pinterest] Loading: %s", url)
            try:
                await page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception:
                logger.warning("[pinterest] Page load timeout, continuing")

            collected = 0
            scroll_attempts = 0
            max_scroll = settings.max_pages * 3

            while collected < settings.max_images_per_source and scroll_attempts < max_scroll:
                images = page.locator("img[src*='pinimg.com']")
                count = await images.count()

                for i in range(count):
                    if collected >= settings.max_images_per_source:
                        break
                    try:
                        img_el = images.nth(i)
                        src = await img_el.get_attribute("src") or ""
                        alt = await img_el.get_attribute("alt") or ""
                        if not src:
                            continue

                        # Upgrade to higher resolution
                        high_res = src.replace("/236x/", "/originals/").replace(
                            "/564x/", "/originals/"
                        )

                        filepath = await self.download_image(high_res)
                        if filepath is None:
                            continue

                        yield CollectedImage(
                            filepath=filepath,
                            source_url=high_res,
                            source_domain="pinterest.com",
                            page_url=url,
                            title=alt,
                            tags=self.search_query.split(),
                            category="web_design",
                            license_type="copyrighted_reference",
                        )
                        collected += 1
                    except Exception:
                        logger.debug("[pinterest] Error processing img %d", i, exc_info=True)

                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                await page.wait_for_timeout(2000)
                scroll_attempts += 1

            await browser.close()
