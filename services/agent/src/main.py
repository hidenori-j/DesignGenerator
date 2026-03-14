from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.routes import generation, health, search

app = FastAPI(
    title="DesignGenerator Agent Service",
    version="0.1.0",
    description="Agentic RAG Orchestrator for AI Design Generation",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:4000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(generation.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")


@app.on_event("startup")
async def startup() -> None:
    print(f"Agent service starting on port {settings.port}")
    print(f"GPU Mode: {settings.gpu_mode}")
    print(f"OpenAI Model: {settings.openai_model}")
