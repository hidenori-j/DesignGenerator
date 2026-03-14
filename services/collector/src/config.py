from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    download_dir: Path = Path("data/collected")
    ingest_service_url: str = "http://localhost:8200"
    request_delay: float = 2.0  # seconds between requests (polite crawling)
    max_pages: int = 10
    max_images_per_source: int = 500
    headless: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
