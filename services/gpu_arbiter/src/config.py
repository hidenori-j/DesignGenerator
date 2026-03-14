from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    port: int = 8300

    gpu_mode: str = "cloud"  # cloud | local | hybrid

    redis_url: str = "redis://localhost:6379"

    # Cloud fallback keys
    openai_api_key: str = ""
    fal_ai_api_key: str = ""

    # Timeouts
    gpu_job_timeout_vlm: int = 120
    gpu_job_timeout_generation: int = 300
    gpu_dlq_max_retries: int = 3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
