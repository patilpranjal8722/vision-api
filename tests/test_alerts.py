"""Test suite for alert evaluation service and alerts API routes."""

import io
from PIL import Image
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.models.alert import Alert
from app.models.detection import Detection
from app.models.user import User
from app.services.alert_service import evaluate_detection


@pytest.fixture
def auth_users(db_session: Session) -> tuple[User, User, User]:
    """Create standard user1, standard user2, and an admin user."""
    u1 = User(
        email="user1_alert@example.com",
        username="user1_alert",
        hashed_password=hash_password("Str0ng!Pass"),
        role="user",
        is_active=True,
    )
    u2 = User(
        email="user2_alert@example.com",
        username="user2_alert",
        hashed_password=hash_password("Str0ng!Pass"),
        role="user",
        is_active=True,
    )
    admin = User(
        email="admin_alert@example.com",
        username="admin_alert",
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


def test_alert_service_threshold_levels(db_session: Session, auth_users: tuple[User, User, User], monkeypatch: pytest.MonkeyPatch) -> None:
    """Test evaluate_detection creates correct levels at warning and critical, and None below."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ALERT_WARNING_THRESHOLD", 5)
    monkeypatch.setattr(settings, "ALERT_CRITICAL_THRESHOLD", 15)

    u1, _, _ = auth_users

    # 1. Below warning threshold -> No alert
    det_low = Detection(
        user_id=u1.id,
        source_type="image",
        detector_name="dummy",
        total_count=4,
    )
    db_session.add(det_low)
    db_session.commit()
    db_session.refresh(det_low)

    alert_low = evaluate_detection(db_session, det_low)
    assert alert_low is None

    # 2. At warning threshold -> Warning alert
    det_warn = Detection(
        user_id=u1.id,
        source_type="image",
        detector_name="dummy",
        total_count=5,
    )
    db_session.add(det_warn)
    db_session.commit()
    db_session.refresh(det_warn)

    alert_warn = evaluate_detection(db_session, det_warn)
    assert alert_warn is not None
    assert alert_warn.level == "warning"
    assert alert_warn.user_id == u1.id
    assert alert_warn.detection_id == det_warn.id
    assert "warning threshold 5" in alert_warn.message

    # 3. At critical threshold -> Critical alert
    det_crit = Detection(
        user_id=u1.id,
        source_type="image",
        detector_name="dummy",
        total_count=15,
    )
    db_session.add(det_crit)
    db_session.commit()
    db_session.refresh(det_crit)

    alert_crit = evaluate_detection(db_session, det_crit)
    assert alert_crit is not None
    assert alert_crit.level == "critical"
    assert alert_crit.user_id == u1.id
    assert alert_crit.detection_id == det_crit.id
    assert "critical threshold 15" in alert_crit.message


def test_post_detect_image_triggers_alert_and_handles_alert_failure(
    client: TestClient,
    auth_users: tuple[User, User, User],
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    """Test POST /detect/image creates alert when threshold is low, and survives alert errors."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ALERT_WARNING_THRESHOLD", 1)  # Low threshold

    u1, _, _ = auth_users
    token = create_access_token(u1.id)

    # Create dummy JPEG image
    img = Image.new("RGB", (200, 200), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    response = client.post(
        "/detect/image",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.jpg", image_bytes, "image/jpeg")},
    )
    assert response.status_code == 201

    # Verify Alert row exists in DB
    db_session.expire_all()
    created_alert = db_session.query(Alert).filter(Alert.user_id == u1.id).first()
    assert created_alert is not None
    assert created_alert.level in ("warning", "critical")

    # Now verify exception inside alert evaluation doesn't fail the detection request
    def broken_evaluate(*args, **kwargs):
        raise RuntimeError("Simulated alert evaluation failure")

    monkeypatch.setattr("app.services.alert_service.evaluate_detection", broken_evaluate)

    response2 = client.post(
        "/detect/image",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test2.jpg", image_bytes, "image/jpeg")},
    )
    assert response2.status_code == 201


def test_alerts_api_crud_pagination_filters_and_access_control(
    client: TestClient,
    auth_users: tuple[User, User, User],
    db_session: Session,
) -> None:
    """Test GET /alerts, /unread-count, PATCH /read, and POST /read-all with RBAC."""
    u1, u2, admin = auth_users
    u1_token = create_access_token(u1.id)
    u2_token = create_access_token(u2.id)
    admin_token = create_access_token(admin.id)

    # 1. Unauthenticated request gives 401
    res_unauth = client.get("/alerts")
    assert res_unauth.status_code == 401

    # 2. Seed alerts for u1 (3 alerts) and u2 (2 alerts)
    a1 = Alert(user_id=u1.id, level="warning", message="User 1 Alert 1", is_read=False)
    a2 = Alert(user_id=u1.id, level="critical", message="User 1 Alert 2", is_read=False)
    a3 = Alert(user_id=u1.id, level="warning", message="User 1 Alert 3", is_read=True)
    a4 = Alert(user_id=u2.id, level="critical", message="User 2 Alert 1", is_read=False)
    a5 = Alert(user_id=u2.id, level="warning", message="User 2 Alert 2", is_read=True)
    db_session.add_all([a1, a2, a3, a4, a5])
    db_session.commit()
    db_session.refresh(a1)
    db_session.refresh(a2)
    db_session.refresh(a3)
    db_session.refresh(a4)
    db_session.refresh(a5)

    # 3. User 1 lists alerts (should see 3 items, newest first)
    res_u1 = client.get("/alerts", headers={"Authorization": f"Bearer {u1_token}"})
    assert res_u1.status_code == 200
    u1_alerts = res_u1.json()
    assert len(u1_alerts) == 3
    assert all(a["user_id"] == u1.id for a in u1_alerts)

    # 4. User 1 checks unread count (2 unread: a1 and a2)
    res_unread = client.get("/alerts/unread-count", headers={"Authorization": f"Bearer {u1_token}"})
    assert res_unread.status_code == 200
    assert res_unread.json()["unread_count"] == 2

    # 5. Filtering by level and is_read
    res_filtered = client.get(
        "/alerts?level=critical&is_read=false",
        headers={"Authorization": f"Bearer {u1_token}"},
    )
    assert res_filtered.status_code == 200
    assert len(res_filtered.json()) == 1
    assert res_filtered.json()[0]["id"] == a2.id

    # 6. Admin sees all alerts (5 items)
    res_admin = client.get("/alerts", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert len(res_admin.json()) == 5

    # 7. Admin unread count sees all unread alerts (a1, a2, a4 = 3 unread)
    res_admin_unread = client.get("/alerts/unread-count", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin_unread.status_code == 200
    assert res_admin_unread.json()["unread_count"] == 3

    # 8. User 2 tries to mark User 1's alert as read -> 404
    res_forbidden_mark = client.patch(
        f"/alerts/{a1.id}/read",
        headers={"Authorization": f"Bearer {u2_token}"},
    )
    assert res_forbidden_mark.status_code == 404

    # 9. User 1 marks own alert as read -> 200
    res_mark = client.patch(
        f"/alerts/{a1.id}/read",
        headers={"Authorization": f"Bearer {u1_token}"},
    )
    assert res_mark.status_code == 200
    assert res_mark.json()["is_read"] is True

    # Check unread count is now 1
    res_unread_after = client.get("/alerts/unread-count", headers={"Authorization": f"Bearer {u1_token}"})
    assert res_unread_after.json()["unread_count"] == 1

    # 10. User 1 calls POST /alerts/read-all
    res_read_all = client.post("/alerts/read-all", headers={"Authorization": f"Bearer {u1_token}"})
    assert res_read_all.status_code == 200
    assert res_read_all.json()["updated_count"] == 1

    # Unread count is now 0
    res_zero = client.get("/alerts/unread-count", headers={"Authorization": f"Bearer {u1_token}"})
    assert res_zero.json()["unread_count"] == 0
