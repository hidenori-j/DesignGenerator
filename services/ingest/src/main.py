from fastapi import FastAPI

from src.qdrant_schema import create_collection_if_not_exists
from src.routes import health, ingest

app = FastAPI(
    title="DesignGenerator Ingest Service",
    version="0.1.0",
    description="Data ingestion: VLM processing, SigLIP-2 embedding, Qdrant indexing",
)

app.include_router(health.router)
app.include_router(ingest.router, prefix="/api/v1")


@app.on_event("startup")
def startup() -> None:
    try:
        create_collection_if_not_exists()
    except Exception as e:
        print(f"Warning: Qdrant collection init failed (is Qdrant running?): {e}")
