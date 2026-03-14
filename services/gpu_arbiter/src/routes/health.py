from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "gpu-arbiter",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
