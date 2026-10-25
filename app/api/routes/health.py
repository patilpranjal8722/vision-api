"""Health and readiness check routes for system liveness, readiness, detector state, and database connectivity."""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.job import Job
from app.services.ws_manager import ws_manager

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check (Liveness)")
@limiter.exempt
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


@router.get("/ready", summary="Readiness Check")
@limiter.exempt
def get_ready(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Return 200 with {'status': 'ready'} only when database responds to SELECT 1 and detector is loaded.

    Otherwise returns HTTP 503 Service Unavailable detailing which dependency failed.
    """
    failed_checks = []

    # 1. Database check
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        failed_checks.append("database")

    # 2. Detector check
    detector = getattr(request.app.state, "detector", None)
    if not (detector and detector.is_loaded):
        failed_checks.append("detector")

    if failed_checks:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service not ready: {', '.join(failed_checks)} check failed",
        )

    return {"status": "ready"}
