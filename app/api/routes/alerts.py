"""Alert management routes: listing, unread counts, and read status updates."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.alert import Alert
from app.models.user import User
from app.schemas.alert import AlertOut, ReadAllOut, UnreadCountOut

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get(
    "",
    response_model=List[AlertOut],
    summary="List alerts with pagination and optional filtering",
)
def list_alerts(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    level: Optional[str] = Query(default=None, description="Filter by alert level ('warning' or 'critical')"),
    is_read: Optional[bool] = Query(default=None, description="Filter by read status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Alert]:
    """Retrieve alerts ordered newest first.

    - Standard users only see their own alerts.
    - Administrators can see alerts for all users.
    - Supports filtering by level and read status.
    """
    db.expire_all()
    query = db.query(Alert)

    if current_user.role != "admin":
        query = query.filter(Alert.user_id == current_user.id)

    if level:
        query = query.filter(Alert.level == level)

    if is_read is not None:
        query = query.filter(Alert.is_read == is_read)

    offset = (page - 1) * limit
    alerts = (
        query.order_by(Alert.created_at.desc(), Alert.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return alerts


@router.get(
    "/unread-count",
    response_model=UnreadCountOut,
    summary="Get count of unread alerts",
)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UnreadCountOut:
    """Return the total number of unread alerts.

    - Standard users receive the count of their own unread alerts.
    - Administrators receive the total unread count across all users.
    """
    db.expire_all()
    query = db.query(Alert).filter(Alert.is_read.is_(False))

    if current_user.role != "admin":
        query = query.filter(Alert.user_id == current_user.id)

    count = query.count()
    return UnreadCountOut(unread_count=count)


@router.patch(
    "/{alert_id}/read",
    response_model=AlertOut,
    summary="Mark a specific alert as read",
)
def mark_alert_as_read(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Alert:
    """Mark an alert as read.

    - Accessible by the alert owner or an administrator.
    - Attempting to mark another user's alert returns HTTP 404.
    """
    db.expire_all()
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    if current_user.role != "admin" and alert.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert


@router.post(
    "/read-all",
    response_model=ReadAllOut,
    summary="Mark all caller alerts as read",
)
def mark_all_alerts_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReadAllOut:
    """Mark all unread alerts belonging to the caller as read."""
    db.expire_all()
    query = db.query(Alert).filter(
        Alert.user_id == current_user.id,
        Alert.is_read.is_(False),
    )
    count = query.count()
    if count > 0:
        query.update({"is_read": True}, synchronize_session=False)
        db.commit()

    return ReadAllOut(
        message="All alerts marked as read",
        updated_count=count,
    )
