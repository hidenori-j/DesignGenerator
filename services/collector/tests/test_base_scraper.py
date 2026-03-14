"""Tests for the base scraper logic."""

import hashlib
from pathlib import Path
from typing import AsyncIterator

import pytest

from src.scrapers.base import BaseScraper, CollectedImage


class DummyScraper(BaseScraper):
    domain = "test"

    async def scrape(self) -> AsyncIterator[CollectedImage]:
        yield CollectedImage(
            filepath=Path("test.png"),
            source_url="https://example.com/test.png",
            source_domain="example.com",
            page_url="https://example.com",
            title="Test Image",
        )


def test_dedup_detection(tmp_path: Path):
    scraper = DummyScraper(download_dir=tmp_path)
    data = b"test image data here"
    assert not scraper._is_duplicate(data)
    assert scraper._is_duplicate(data)  # second call should detect duplicate


def test_load_existing_hashes(tmp_path: Path):
    test_file = tmp_path / "existing.png"
    test_file.write_bytes(b"existing file content")

    scraper = DummyScraper(download_dir=tmp_path)
    assert len(scraper._seen_hashes) == 1

    h = hashlib.sha256(b"existing file content").hexdigest()
    assert h in scraper._seen_hashes


def test_collected_image_defaults():
    img = CollectedImage(
        filepath=Path("test.png"),
        source_url="https://example.com/img.png",
        source_domain="example.com",
        page_url="https://example.com",
    )
    assert img.license_type == "copyrighted_reference"
    assert img.category == "unknown"
    assert img.tags == []
