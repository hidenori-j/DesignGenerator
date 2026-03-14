from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    collection_name: str = "design_assets"
    vector_size: int = 512  # CLIP ViT-B/32; production SigLIP-2 uses 1152

    # Redis
    redis_url: str = "redis://localhost:6379"

    # MinIO (optional)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "design-assets"
    minio_secure: bool = False

    # Embedding model (dev: sentence-transformers CLIP; prod: SigLIP-2 via GPU)
    embedding_model_name: str = "sentence-transformers/clip-ViT-B-32"

    # GPU Arbiter (optional, for heavy VLM/embedding)
    gpu_arbiter_url: str = "http://localhost:8300"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
