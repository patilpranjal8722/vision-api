"""Alert evaluation service for computer vision detection events."""

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.alert import Alert
from app.models.detection import Detection
from app.services.ws_manager import ws_manager

logger = get_logger("vision_api.alert_service")


def evaluate_detection(db: Session, detection: Detection) -> Optional[Alert]:
    """Evaluate detection object count against warning and critical thresholds.

    Creates an Alert record if threshold is met, commits it, and pushes it via WebSocket.
    Returns the created Alert or None.
    """
    settings = get_settings()

    level: Optional[str] = None
    threshold: Optional[int] = None

    if detection.total_count >= settings.ALERT_CRITICAL_THRESHOLD:
        level = "critical"
        threshold = settings.ALERT_CRITICAL_THRESHOLD
    elif detection.total_count >= settings.ALERT_WARNING_THRESHOLD:
        level = "warning"
        threshold = settings.ALERT_WARNING_THRESHOLD

    if level is None or threshold is None:
        return None

    message = f"{detection.total_count} objects detected ({level} threshold {threshold})"

    alert = Alert(
        user_id=detection.user_id,
        detection_id=detection.id,
        level=level,
        message=message,
        is_read=False,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    logger.info(
        "Alert created",
        extra={
            "alert_id": alert.id,
            "level": alert.level,
            "user_id": alert.user_id,
            "detection_id": alert.detection_id,
            "total_count": detection.total_count,
        },
    )

    # Push to connected WebSocket clients thread-safely
    try:
        alert_dict: Dict[str, Any] = {
            "id": alert.id,
            "user_id": alert.user_id,
            "detection_id": alert.detection_id,
            "level": alert.level,
            "message": alert.message,
            "is_read": alert.is_read,
            "created_at": alert.created_at.isoformat(),
        }
        ws_manager.push_alert_threadsafe(alert_dict, alert.user_id)
    except Exception as exc:
        logger.error(f"Failed to push alert to WebSocket clients: {exc}", exc_info=True)

    return alert
