"""Analytics routes: aggregated metrics and timeseries buckets."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.alert import Alert
from app.models.detection import Detection
from app.models.user import User
from app.schemas.analytics import AnalyticsSummaryOut, TimeseriesBucket

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _parse_and_validate_date_range(
    date_from: Optional[datetime],
    date_to: Optional[datetime],
) -> tuple[datetime, datetime]:
    """Parse and validate date_from and date_to parameters."""
    settings = get_settings()

    if date_to is None:
        date_to = datetime.now(timezone.utc)
    elif date_to.tzinfo is None:
        date_to = date_to.replace(tzinfo=timezone.utc)

    if date_from is None:
        date_from = date_to - timedelta(days=7)
    elif date_from.tzinfo is None:
        date_from = date_from.replace(tzinfo=timezone.utc)

    if date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from cannot be after date_to",
        )

    max_seconds = settings.ANALYTICS_MAX_RANGE_DAYS * 86400
    if (date_to - date_from).total_seconds() > max_seconds:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Date range exceeds maximum allowed limit of {settings.ANALYTICS_MAX_RANGE_DAYS} days",
        )

    return date_from, date_to


@router.get(
    "/summary",
    response_model=AnalyticsSummaryOut,
    summary="Get aggregated detection and alert analytics summary",
)
def get_analytics_summary(
    date_from: Optional[datetime] = Query(default=None, description="Start date (ISO format, default: 7 days ago)"),
    date_to: Optional[datetime] = Query(default=None, description="End date (ISO format, default: now)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalyticsSummaryOut:
    """Retrieve summarized statistics across detections and alerts.

    - Standard users see only their own data.
    - Administrators see statistics aggregated across all users.
    """
    settings = get_settings()
    d_from, d_to = _parse_and_validate_date_range(date_from, date_to)

    # Compute scalar aggregates (COUNT, SUM, MAX) in one query directly on the database
    agg_query = (
        db.query(
            func.count(Detection.id),
            func.coalesce(func.sum(Detection.total_count), 0),
            func.coalesce(func.max(Detection.total_count), 0),
        )
        .filter(
            Detection.created_at >= d_from,
            Detection.created_at <= d_to,
        )
    )
    if current_user.role != "admin":
        agg_query = agg_query.filter(Detection.user_id == current_user.id)

    total_detections, total_objects, max_count = agg_query.one()
    total_detections = int(total_detections or 0)
    total_objects = int(total_objects or 0)
    max_count = int(max_count or 0)
    avg_count = round(total_objects / total_detections, 2) if total_detections > 0 else 0.0

    # Source breakdown via GROUP BY source_type
    source_query = (
        db.query(Detection.source_type, func.count(Detection.id))
        .filter(
            Detection.created_at >= d_from,
            Detection.created_at <= d_to,
        )
    )
    if current_user.role != "admin":
        source_query = source_query.filter(Detection.user_id == current_user.id)

    source_rows = source_query.group_by(Detection.source_type).all()
    counts_by_source: Dict[str, int] = {"image": 0, "video": 0, "stream": 0}
    for src, cnt in source_rows:
        counts_by_source[src] = int(cnt)

    # Alerts counted by level via GROUP BY level
    alert_query = (
        db.query(Alert.level, func.count(Alert.id))
        .filter(
            Alert.created_at >= d_from,
            Alert.created_at <= d_to,
        )
    )
    if current_user.role != "admin":
        alert_query = alert_query.filter(Alert.user_id == current_user.id)

    alert_rows = alert_query.group_by(Alert.level).all()
    alerts_by_level: Dict[str, int] = {"warning": 0, "critical": 0}
    for lvl, cnt in alert_rows:
        alerts_by_level[lvl] = int(cnt)

    # For top_labels, select ONLY results and source_type for rows where total_count > 0, capped to ANALYTICS_MAX_ROWS
    label_query = (
        db.query(Detection.results, Detection.source_type)
        .filter(
            Detection.created_at >= d_from,
            Detection.created_at <= d_to,
            Detection.total_count > 0,
        )
    )
    if current_user.role != "admin":
        label_query = label_query.filter(Detection.user_id == current_user.id)

    raw_label_rows = (
        label_query.order_by(Detection.created_at.asc())
        .limit(settings.ANALYTICS_MAX_ROWS + 1)
        .all()
    )
    truncated = len(raw_label_rows) > settings.ANALYTICS_MAX_ROWS
    label_rows = raw_label_rows[: settings.ANALYTICS_MAX_ROWS]

    # Top labels extraction from sample
    label_counter: Counter[str] = Counter()
    for res, source_type in label_rows:
        res = res or {}
        if source_type == "video":
            peak = res.get("peak_frame") or {}
            objs = peak.get("objects") or []
        else:
            objs = res.get("objects") or []

        for obj in objs:
            if isinstance(obj, dict) and "label" in obj:
                label_counter[obj["label"]] += 1

    top_labels = dict(label_counter.most_common())

    return AnalyticsSummaryOut(
        total_detections=total_detections,
        total_objects=total_objects,
        avg_count=avg_count,
        max_count=max_count,
        counts_by_source=counts_by_source,
        alerts_by_level=alerts_by_level,
        top_labels=top_labels,
        truncated=truncated,
    )


@router.get(
    "/timeseries",
    response_model=List[TimeseriesBucket],
    summary="Get timeseries buckets for detections",
)
def get_analytics_timeseries(
    interval: str = Query(default="hour", description="Bucket interval: 'hour' or 'day'"),
    date_from: Optional[datetime] = Query(default=None, description="Start date (ISO format, default: 7 days ago)"),
    date_to: Optional[datetime] = Query(default=None, description="End date (ISO format, default: now)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TimeseriesBucket]:
    """Retrieve timeseries detection metrics bucketed by hour or day.

    Empty buckets are zero-filled to eliminate gaps in frontend charts.
    """
    if interval not in ("hour", "day"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Interval must be 'hour' or 'day'",
        )

    settings = get_settings()
    d_from, d_to = _parse_and_validate_date_range(date_from, date_to)

    # Select only scalar columns (created_at, total_count) instead of full ORM instances with JSON results
    det_query = (
        db.query(Detection.created_at, Detection.total_count)
        .filter(
            Detection.created_at >= d_from,
            Detection.created_at <= d_to,
        )
    )
    if current_user.role != "admin":
        det_query = det_query.filter(Detection.user_id == current_user.id)

    raw_detections = (
        det_query.order_by(Detection.created_at.asc())
        .limit(settings.ANALYTICS_MAX_ROWS)
        .all()
    )

    # Pre-populate all continuous buckets to ensure no gaps
    step = timedelta(hours=1) if interval == "hour" else timedelta(days=1)
    if interval == "hour":
        curr = d_from.replace(minute=0, second=0, microsecond=0)
    else:
        curr = d_from.replace(hour=0, minute=0, second=0, microsecond=0)

    bucket_data: Dict[datetime, Dict[str, Any]] = {}
    while curr <= d_to:
        bucket_data[curr] = {"detections": 0, "total_objects": 0, "max_count": 0}
        curr += step

    # Populate buckets from query results
    for c_at, total_count in raw_detections:
        if c_at.tzinfo is None:
            c_at = c_at.replace(tzinfo=timezone.utc)
        else:
            c_at = c_at.astimezone(timezone.utc)

        if interval == "hour":
            key = c_at.replace(minute=0, second=0, microsecond=0)
        else:
            key = c_at.replace(hour=0, minute=0, second=0, microsecond=0)

        if key in bucket_data:
            bucket_data[key]["detections"] += 1
            bucket_data[key]["total_objects"] += (total_count or 0)
            bucket_data[key]["max_count"] = max(bucket_data[key]["max_count"], (total_count or 0))

    result_buckets: List[TimeseriesBucket] = []
    for b_time in sorted(bucket_data.keys()):
        item = bucket_data[b_time]
        dets = item["detections"]
        avg_cnt = round(item["total_objects"] / dets, 2) if dets > 0 else 0.0
        result_buckets.append(
            TimeseriesBucket(
                bucket_start=b_time.isoformat(),
                detections=dets,
                avg_count=avg_cnt,
                max_count=item["max_count"],
            )
        )

    return result_buckets
