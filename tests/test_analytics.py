"""Test suite for analytics summary, timeseries bucketing, and range validations."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.models.alert import Alert
from app.models.detection import Detection
from app.models.user import User


@pytest.fixture
def analytics_users(db_session: Session) -> tuple[User, User, User]:
    """Create two normal users and one admin user."""
    u1 = User(
        email="analytics_u1@example.com",
        username="analytics_u1",
        hashed_password=hash_password("Str0ng!Pass"),
        role="user",
        is_active=True,
    )
    u2 = User(
        email="analytics_u2@example.com",
        username="analytics_u2",
        hashed_password=hash_password("Str0ng!Pass"),
        role="user",
        is_active=True,
    )
    admin = User(
        email="analytics_admin@example.com",
        username="analytics_admin",
        hashed_password=hash_password("Str0ng!Pass"),
        role="admin",
        is_active=True,
    )
    db_session.add_all([u1, u2, admin])
    db_session.commit()
    db_session.refresh(u1)
    db_session.refresh(u2)
    db_session.refresh(admin)
    return u1, u2, admin


def test_analytics_summary_known_values_and_top_labels(
    client: TestClient,
    analytics_users: tuple[User, User, User],
    db_session: Session,
) -> None:
    """Test /analytics/summary returns exact aggregates, sources, alerts, and top labels."""
    u1, u2, admin = analytics_users
    u1_token = create_access_token(u1.id)
    admin_token = create_access_token(admin.id)

    now = datetime.now(timezone.utc)

    # User 1 detections
    d1 = Detection(
        user_id=u1.id,
        source_type="image",
        detector_name="dummy",
        total_count=3,
        results={"objects": [{"label": "person"}, {"label": "person"}, {"label": "car"}]},
        created_at=now - timedelta(hours=2),
    )
    d2 = Detection(
        user_id=u1.id,
        source_type="video",
        detector_name="dummy",
        total_count=5,
        results={"peak_frame": {"objects": [{"label": "person"}, {"label": "dog"}, {"label": "dog"}]}},
        created_at=now - timedelta(hours=1),
    )
    # User 2 detection
    d3 = Detection(
        user_id=u2.id,
        source_type="stream",
        detector_name="dummy",
        total_count=10,
        results={"objects": [{"label": "bicycle"}]},
        created_at=now - timedelta(minutes=30),
    )
    # User 1 alert
    a1 = Alert(
        user_id=u1.id,
        level="warning",
        message="Warning 1",
        created_at=now - timedelta(hours=1),
    )
    db_session.add_all([d1, d2, d3, a1])
    db_session.commit()

    # 1. User 1 summary (should only see d1 and d2)
    res_u1 = client.get("/analytics/summary", headers={"Authorization": f"Bearer {u1_token}"})
    assert res_u1.status_code == 200
    data_u1 = res_u1.json()

    assert data_u1["total_detections"] == 2
    assert data_u1["total_objects"] == 8  # 3 + 5
    assert data_u1["avg_count"] == 4.0  # 8 / 2
    assert data_u1["max_count"] == 5
    assert data_u1["counts_by_source"] == {"image": 1, "video": 1, "stream": 0}
    assert data_u1["alerts_by_level"]["warning"] == 1
    assert data_u1["truncated"] is False

    # Check top labels for u1: person=3 (2 from image + 1 from video peak), dog=2, car=1
    assert data_u1["top_labels"]["person"] == 3
    assert data_u1["top_labels"]["dog"] == 2
    assert data_u1["top_labels"]["car"] == 1
    assert "bicycle" not in data_u1["top_labels"]

    # 2. Admin summary sees all 3 detections
    res_admin = client.get("/analytics/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    data_admin = res_admin.json()
    assert data_admin["total_detections"] == 3
    assert data_admin["total_objects"] == 18
    assert data_admin["top_labels"]["bicycle"] == 1


def test_analytics_timeseries_fills_empty_buckets(
    client: TestClient,
    analytics_users: tuple[User, User, User],
    db_session: Session,
) -> None:
    """Test /analytics/timeseries creates continuous zero-filled buckets across date range."""
    u1, _, _ = analytics_users
    token = create_access_token(u1.id)

    # 24-hour test range
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(hours=24)

    # Insert 1 detection 2 hours ago
    det = Detection(
        user_id=u1.id,
        source_type="image",
        detector_name="dummy",
        total_count=7,
        created_at=now - timedelta(hours=2),
    )
    db_session.add(det)
    db_session.commit()

    res = client.get(
        "/analytics/timeseries",
        params={"interval": "hour", "date_from": start.isoformat(), "date_to": now.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    buckets = res.json()
    assert isinstance(buckets, list)

    # 24 hours plus endpoint means at least 25 hourly buckets
    assert len(buckets) >= 25

    # Check that empty buckets have detections == 0
    empty_buckets = [b for b in buckets if b["detections"] == 0]
    assert len(empty_buckets) >= 24
    for eb in empty_buckets:
        assert eb["avg_count"] == 0.0
        assert eb["max_count"] == 0

    # Check the populated bucket
    active_buckets = [b for b in buckets if b["detections"] == 1]
    assert len(active_buckets) == 1
    assert active_buckets[0]["max_count"] == 7
    assert active_buckets[0]["avg_count"] == 7.0


def test_analytics_validations(
    client: TestClient,
    analytics_users: tuple[User, User, User],
) -> None:
    """Test invalid interval, reversed dates, and excessive range return 422."""
    u1, _, _ = analytics_users
    token = create_access_token(u1.id)

    # 1. Invalid interval
    res_bad_interval = client.get(
        "/analytics/timeseries?interval=month",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_bad_interval.status_code == 422
    assert "interval" in res_bad_interval.json()["detail"].lower()

    # 2. date_from after date_to
    now = datetime.now(timezone.utc)
    res_reversed = client.get(
        "/analytics/summary",
        params={"date_from": (now + timedelta(days=1)).isoformat(), "date_to": now.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_reversed.status_code == 422
    assert "date_from cannot be after date_to" in res_reversed.json()["detail"]

    # 3. Range longer than ANALYTICS_MAX_RANGE_DAYS (90 days)
    res_too_long = client.get(
        "/analytics/summary",
        params={"date_from": (now - timedelta(days=95)).isoformat(), "date_to": now.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_too_long.status_code == 422
    assert "exceeds maximum allowed limit" in res_too_long.json()["detail"]


def test_analytics_truncation_flag(
    client: TestClient,
    analytics_users: tuple[User, User, User],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that summary sets truncated=True when row limit is hit."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ANALYTICS_MAX_ROWS", 2)  # Tiny limit for testing

    u1, _, _ = analytics_users
    token = create_access_token(u1.id)

    # Insert 3 detections
    now = datetime.now(timezone.utc)
    for i in range(3):
        db_session.add(
            Detection(
                user_id=u1.id,
                source_type="image",
                detector_name="dummy",
                total_count=i + 1,
                created_at=now - timedelta(minutes=i),
            )
        )
    db_session.commit()

    res = client.get("/analytics/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["truncated"] is True
    # Totals cover the entire date range (3 rows) instead of being clamped to ANALYTICS_MAX_ROWS (2)
    assert res.json()["total_detections"] == 3


def test_analytics_summary_totals_exceed_max_rows_and_scoping(
    client: TestClient,
    analytics_users: tuple[User, User, User],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test totals cover the whole date range when exceeding ANALYTICS_MAX_ROWS and verify user vs admin scoping."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ANALYTICS_MAX_ROWS", 2)  # Tiny cap for testing

    u1, u2, admin = analytics_users
    u1_token = create_access_token(u1.id)
    admin_token = create_access_token(admin.id)

    now = datetime.now(timezone.utc)

    # 4 detections for u1: total_counts = [2, 4, 6, 8] -> sum=20, max=8, avg=5.0
    for i, count in enumerate([2, 4, 6, 8]):
        db_session.add(
            Detection(
                user_id=u1.id,
                source_type="image" if i % 2 == 0 else "video",
                detector_name="dummy",
                total_count=count,
                results={"objects": [{"label": "cat"}]} if i % 2 == 0 else {"peak_frame": {"objects": [{"label": "bird"}]}},
                created_at=now - timedelta(minutes=10 * (i + 1)),
            )
        )

    # 3 detections for u2: total_counts = [10, 20, 30] -> sum=60
    for i, count in enumerate([10, 20, 30]):
        db_session.add(
            Detection(
                user_id=u2.id,
                source_type="stream",
                detector_name="dummy",
                total_count=count,
                results={"objects": [{"label": "truck"}]},
                created_at=now - timedelta(minutes=5 * (i + 1)),
            )
        )
    db_session.commit()

    # User 1 query: should see only u1's 4 detections despite ANALYTICS_MAX_ROWS=2
    res_u1 = client.get("/analytics/summary", headers={"Authorization": f"Bearer {u1_token}"})
    assert res_u1.status_code == 200
    data_u1 = res_u1.json()
    assert data_u1["total_detections"] == 4  # All 4 u1 rows counted (exceeds cap of 2)
    assert data_u1["total_objects"] == 20    # 2 + 4 + 6 + 8
    assert data_u1["avg_count"] == 5.0
    assert data_u1["max_count"] == 8
    assert data_u1["counts_by_source"] == {"image": 2, "video": 2, "stream": 0}
    assert data_u1["truncated"] is True     # Sample for top_labels was capped at 2
    assert "truck" not in data_u1["top_labels"]

    # Admin query: should aggregate across all users (4 from u1 + 3 from u2 = 7)
    res_admin = client.get("/analytics/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    data_admin = res_admin.json()
    assert data_admin["total_detections"] == 7
    assert data_admin["total_objects"] == 80  # 20 + 60
    assert data_admin["max_count"] == 30
    assert data_admin["counts_by_source"] == {"image": 2, "video": 2, "stream": 3}
    assert data_admin["truncated"] is True

