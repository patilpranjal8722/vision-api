"""Health check route for system liveness and readiness verification."""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check")
async def get_health(
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Return application operational status, metadata, and model readiness.

    Returns:
        JSON response with status, app_name, version, timestamp, and model_loaded.
    """
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_loaded": False,
    }
