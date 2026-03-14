import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from src.config import log_startup_config
from src.routes.generate import router as generate_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    log_startup_config()
    yield


app = FastAPI(
    title="DesignGenerator Generation Engine",
    version="0.2.0",
    description="Image generation: cloud API routing (Fal.ai FLUX.2 Pro), model routing, MinIO storage",
    lifespan=lifespan,
)

app.include_router(generate_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "generation"}
