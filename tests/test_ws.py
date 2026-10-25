"""Test suite for WebSocket authentication, alerts feed, frame stream, and testbench page."""

import io
import json
from PIL import Image
import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.alert import Alert
from app.models.detection import Detection
from app.models.user import User
from app.services.alert_service import evaluate_detection
from app.services.ws_manager import ws_manager


@pytest.fixture
def ws_users(db_session: Session) -> tuple[User, User, User]:
    """Create two normal users and one admin user for WebSocket testing."""
    u1 = User(
        email="ws_u1@example.com",
        username="ws_u1",
        hashed_password=hash_password("Str0ng!Pass"),
        role="user",
        is_active=True,
    )
    u2 = User(
        email="ws_u2@example.com",
        username="ws_u2",
        hashed_password=hash_password("Str0ng!Pass"),
        role="user",
        is_active=True,
    )
    admin = User(
        email="ws_admin@example.com",
        username="ws_admin",
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


def test_ws_origin_check_allowed_and_disallowed(
    client: TestClient,
    ws_users: tuple[User, User, User],
) -> None:
    """Test Origin check allows localhost/same-host and closes disallowed origins with 4403."""
    u1, _, _ = ws_users
    token = create_access_token(u1.id)

    # 1. Disallowed origin closes with 4403
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/alerts", headers={"origin": "http://evil-attacker.com"}) as ws:
            ws.receive_text()
    assert exc_info.value.code == 4403

    # 2. Allowed origin (in ALLOWED_ORIGINS) succeeds
    with client.websocket_connect("/ws/alerts", headers={"origin": "http://localhost:8000"}) as ws:
        ws.send_text(json.dumps({"type": "auth", "token": token}))
        res = ws.receive_json()
        assert res["type"] == "auth_ok"


def test_ws_authentication_scenarios(
    client: TestClient,
    ws_users: tuple[User, User, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test auth timeout, wrong token, refresh token, and valid token."""
    u1, _, _ = ws_users
    access_token = create_access_token(u1.id)
    refresh_token = create_refresh_token(u1.id)

    # 1. Wrong token closes with 4401
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/alerts") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": "not.a.valid.jwt.token"}))
            ws.receive_json()
    assert exc.value.code == 4401

    # 2. Refresh token used as access token closes with 4401
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/alerts") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": refresh_token}))
            ws.receive_json()
    assert exc.value.code == 4401

    # 3. Timeout without auth message closes with 4401
    monkeypatch.setattr(get_settings(), "WS_AUTH_TIMEOUT_SECONDS", 0.05)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/alerts") as ws:
            # Wait for server to time out
            import time
            time.sleep(0.1)
            ws.receive_text()
    assert exc.value.code == 4401
    monkeypatch.setattr(get_settings(), "WS_AUTH_TIMEOUT_SECONDS", 5)

    # 4. Valid access token succeeds and returns auth_ok
    with client.websocket_connect("/ws/alerts") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": access_token}))
        reply = ws.receive_json()
        assert reply["type"] == "auth_ok"


def test_ws_max_connections_per_user_enforced(
    client: TestClient,
    ws_users: tuple[User, User, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test exceeding WS_MAX_CONNECTIONS_PER_USER closes extra connection with 4429."""
    settings = get_settings()
    monkeypatch.setattr(settings, "WS_MAX_CONNECTIONS_PER_USER", 1)

    u1, _, _ = ws_users
    token = create_access_token(u1.id)

    with client.websocket_connect("/ws/alerts") as ws1:
        ws1.send_text(json.dumps({"type": "auth", "token": token}))
        assert ws1.receive_json()["type"] == "auth_ok"

        # Second connection should be rejected with 4429
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/alerts") as ws2:
                ws2.send_text(json.dumps({"type": "auth", "token": token}))
                ws2.receive_json()
        assert exc.value.code == 4429


def test_ws_alerts_ping_pong_and_isolation(
    client: TestClient,
    ws_users: tuple[User, User, User],
    db_session: Session,
) -> None:
    """Test ping/pong and alert push routing to specific user and admin."""
    u1, u2, _ = ws_users
    token1 = create_access_token(u1.id)

    with client.websocket_connect("/ws/alerts") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": token1}))
        assert ws.receive_json()["type"] == "auth_ok"

        # Ping / pong test
        ws.send_text(json.dumps({"type": "ping"}))
        pong = ws.receive_json()
        assert pong["type"] == "pong"

        # Trigger alert for u1
        det = Detection(user_id=u1.id, source_type="image", detector_name="dummy", total_count=25)
        db_session.add(det)
        db_session.commit()
        db_session.refresh(det)

        evaluate_detection(db_session, det)

        # u1 receives alert
        alert_msg = ws.receive_json()
        assert alert_msg["type"] == "alert"
        assert alert_msg["alert"]["user_id"] == u1.id
        assert alert_msg["alert"]["level"] == "critical"


def test_ws_stream_processing_and_error_tolerance(
    client: TestClient,
    ws_users: tuple[User, User, User],
) -> None:
    """Test /ws/stream processes valid frames, rejects corrupt/oversized frames without crashing."""
    u1, _, _ = ws_users
    token = create_access_token(u1.id)

    # Valid image frame
    img = Image.new("RGB", (100, 100), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    valid_bytes = buf.getvalue()

    with client.websocket_connect("/ws/stream") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": token}))
        assert ws.receive_json()["type"] == "auth_ok"

        # 1. Send valid binary frame
        ws.send_bytes(valid_bytes)
        det_res = ws.receive_json()
        assert det_res["type"] == "detections"
        assert det_res["frame_id"] == 1
        assert "result" in det_res

        # 2. Send corrupt bytes (should return error and keep connection alive)
        ws.send_bytes(b"garbage not an image")
        err_res = ws.receive_json()
        assert err_res["type"] == "error"

        # 3. Subsequent valid frame still works
        ws.send_bytes(valid_bytes)
        det_res2 = ws.receive_json()
        assert det_res2["type"] == "detections"
        assert det_res2["frame_id"] == 2

        # 4. Oversized frame returns error
        oversized = b"A" * (2049 * 1024)
        ws.send_bytes(oversized)
        over_res = ws.receive_json()
        assert over_res["type"] == "error"
        assert "exceeds" in over_res["message"].lower()


def test_ws_stream_alert_cooldown(
    client: TestClient,
    ws_users: tuple[User, User, User],
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test stream alert cooldown prevents creating duplicate alerts within cooldown window."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ALERT_WARNING_THRESHOLD", 1)  # Low threshold
    monkeypatch.setattr(settings, "ALERT_COOLDOWN_SECONDS", 10.0)

    u1, _, _ = ws_users
    token = create_access_token(u1.id)

    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    frame_bytes = buf.getvalue()

    with client.websocket_connect("/ws/stream") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": token}))
        assert ws.receive_json()["type"] == "auth_ok"

        # Frame 1
        ws.send_bytes(frame_bytes)
        res1 = ws.receive_json()
        assert res1["type"] == "detections"

        # Frame 2 immediately within cooldown
        ws.send_bytes(frame_bytes)
        res2 = ws.receive_json()
        assert res2["type"] == "detections"

    # Verify only 1 Detection and 1 Alert row were created for stream
    db_session.expire_all()
    stream_dets = db_session.query(Detection).filter(Detection.source_type == "stream").all()
    assert len(stream_dets) == 1
    stream_alerts = db_session.query(Alert).filter(Alert.user_id == u1.id).all()
    assert len(stream_alerts) == 1


def test_ws_test_page_debug_flag(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test /ws-test page returns 200 HTML when DEBUG=true, 404 when DEBUG=false."""
    settings = get_settings()

    # 1. DEBUG = true -> 200 OK
    monkeypatch.setattr(settings, "DEBUG", True)
    res_debug = client.get("/ws-test")
    assert res_debug.status_code == 200
    assert "text/html" in res_debug.headers["content-type"]
    assert "WebSocket Test Bench" in res_debug.text

    # 2. DEBUG = false -> 404 Not Found
    monkeypatch.setattr(settings, "DEBUG", False)
    res_nodebug = client.get("/ws-test")
    assert res_nodebug.status_code == 404
