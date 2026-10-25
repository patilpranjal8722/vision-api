"""Health check route for system liveness, readiness, detector state, and database connectivity."""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.job import Job
from app.services.ws_manager import ws_manager

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check")
def get_health(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Return application operational status, metadata, model readiness, database health, and WS connections.

    Performs a lightweight `SELECT 1` query to verify database connectivity,
    inspects app.state.detector for model readiness, counts active jobs, and counts open WebSockets.
    If the database is unreachable or the detector failed to load, the endpoint
    reports status 'degraded' without crashing.

    Returns:
        JSON response with status ('ok' or 'degraded'), app_name, version,
        timestamp, detector, model_loaded, detector_is_placeholder, database,
        active_jobs, and ws_connections.
    """
    db_status = "ok"
    active_jobs = 0
    try:
        db.execute(text("SELECT 1"))
        active_jobs = (
            db.query(Job)
            .filter(Job.status.in_(["pending", "running"]))
            .count()
        )
    except Exception:
        db_status = "error"
        active_jobs = 0

    detector = getattr(request.app.state, "detector", None)
    model_loaded = bool(detector and detector.is_loaded)
    detector_name = detector.name if detector else None
    detector_is_placeholder = bool(detector and detector.is_placeholder)

    overall_status = "ok" if (db_status == "ok" and model_loaded) else "degraded"
    ws_connections = ws_manager.get_total_connections()

    return {
        "status": overall_status,
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "detector": detector_name,
        "model_loaded": model_loaded,
        "detector_is_placeholder": detector_is_placeholder,
        "database": db_status,
        "active_jobs": active_jobs,
        "ws_connections": ws_connections,
    }
