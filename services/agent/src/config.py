from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    port: int = 8000

    # GPU
    gpu_mode: str = "hybrid"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/designgen"

    # Downstream services
    generation_service_url: str = "http://localhost:8100"
    ingest_service_url: str = "http://localhost:8200"
    gpu_arbiter_url: str = "http://localhost:8300"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
