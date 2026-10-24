"""Health check route for system liveness, readiness, and database connectivity."""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check")
def get_health(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return application operational status, metadata, model readiness, and database health.

    Performs a lightweight `SELECT 1` query to verify database connectivity.
    If the database is unreachable, the endpoint handles the exception gracefully,
    reporting status 'degraded' and database 'error' without crashing.

    Returns:
        JSON response with status ('ok' or 'degraded'), app_name, version,
        timestamp, model_loaded, and database ('ok' or 'error').
    """
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    overall_status = "ok" if db_status == "ok" else "degraded"

    return {
        "status": overall_status,
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_loaded": False,
        "database": db_status,
    }
