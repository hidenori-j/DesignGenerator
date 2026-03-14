import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    port: int = 8100

    gpu_mode: str = "cloud"  # cloud | local | hybrid

    # Fal.ai
    fal_ai_api_key: str = ""

    # MinIO (S3-compatible)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_generated: str = "generated-outputs"
    minio_use_ssl: bool = False

    # GPU Arbiter
    gpu_arbiter_url: str = "http://localhost:8300"

    # Redis
    redis_url: str = "redis://localhost:6379"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def log_startup_config() -> None:
    """Log the active configuration matrix at startup."""
    fal_status = "CONFIGURED" if settings.fal_ai_api_key else "NOT SET (mock mode)"
    logger.warning(
        "=== Generation Service Config ===\n"
        "  GPU_MODE:        %s\n"
        "  FAL_AI_API_KEY:  %s\n"
        "  MinIO:           %s (bucket: %s)\n"
        "  GPU Arbiter:     %s\n"
        "=================================",
        settings.gpu_mode,
        fal_status,
        settings.minio_endpoint,
        settings.minio_bucket_generated,
        settings.gpu_arbiter_url,
    )
