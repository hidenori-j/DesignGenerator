"""Dribbble gallery scraper using Playwright."""

import logging
from collections.abc import AsyncIterator

from playwright.async_api import async_playwright

from src.config import settings
from src.scrapers.base import BaseScraper, CollectedImage

logger = logging.getLogger(__name__)


class DribbbleScraper(BaseScraper):
    domain = "dribbble"

    def __init__(self, search_query: str = "web design", **kwargs):
        super().__init__(**kwargs)
        self.search_query = search_query

    async def scrape(self) -> AsyncIterator[CollectedImage]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            for page_num in range(1, settings.max_pages + 1):
                url = f"https://dribbble.com/search/{self.search_query}?page={page_num}"
                logger.info("[dribbble] Loading page %d: %s", page_num, url)
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30_000)
                except Exception:
                    logger.warning("[dribbble] Page load timeout, continuing")

                shot_cards = page.locator("li.shot-thumbnail-container")
                count = await shot_cards.count()
                if count == 0:
                    logger.info("[dribbble] No more results at page %d", page_num)
                    break

                for i in range(count):
                    card = shot_cards.nth(i)
                    try:
                        img_el = card.locator("img").first
                        src = await img_el.get_attribute("src") or ""
                        alt = await img_el.get_attribute("alt") or ""
                        if not src or "gif" in src:
                            continue

                        # Dribbble serves different sizes; request the larger one
                        high_res_url = src.replace("/small/", "/original/").replace(
                            "/teaser/", "/original/"
                        )

                        filepath = await self.download_image(high_res_url)
                        if filepath is None:
                            continue

                        link_el = card.locator("a").first
                        page_url = await link_el.get_attribute("href") or ""
                        if page_url and not page_url.startswith("http"):
                            page_url = f"https://dribbble.com{page_url}"

                        yield CollectedImage(
                            filepath=filepath,
                            source_url=high_res_url,
                            source_domain="dribbble.com",
                            page_url=page_url,
                            title=alt,
                            tags=self.search_query.split(),
                            category="web_design",
                            license_type="copyrighted_reference",
                        )
                    except Exception:
                        logger.debug("[dribbble] Error processing card %d", i, exc_info=True)

            await browser.close()
