"""Comprehensive tests for the /detect API endpoints."""

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.models.detection import Detection
from app.models.user import User


def _generate_image_bytes(
    width: int = 120,
    height: int = 80,
    format: str = "JPEG",
    color: str = "blue",
) -> bytes:
    """Generate in-memory encoded image bytes using Pillow."""
    buffer = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buffer, format=format)
    return buffer.getvalue()


@pytest.fixture
def test_users(db_session: Session) -> dict[str, User]:
    """Create a standard user, a second user, and an admin user in the test database."""
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password=hash_password("password123"),
        role="user",
        is_active=True,
    )
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password=hash_password("password123"),
        role="user",
        is_active=True,
    )
    admin = User(
        email="admin@example.com",
        username="admin",
        hashed_password=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db_session.add_all([user1, user2, admin])
    db_session.commit()
    db_session.refresh(user1)
    db_session.refresh(user2)
    db_session.refresh(admin)
    return {"user1": user1, "user2": user2, "admin": admin}


def _auth_header(user: User) -> dict[str, str]:
    """Generate Bearer authorization header for a test user."""
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# POST /detect/image Tests
# ==============================================================================

def test_detect_image_requires_authentication(client: TestClient) -> None:
    """Test that POST /detect/image returns HTTP 401 Unauthorized without token."""
    img_bytes = _generate_image_bytes()
    response = client.post(
        "/detect/image",
        files={"file": ("test.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 401


def test_detect_image_success(
    client: TestClient,
    test_users: dict[str, User],
    db_session: Session,
) -> None:
    """Test successful image detection returns HTTP 201, DB row, and file on disk."""
    user = test_users["user1"]
    headers = _auth_header(user)
    img_bytes = _generate_image_bytes(width=200, height=150, format="JPEG")

    response = client.post(
        "/detect/image",
        headers=headers,
        files={"file": ("sample.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 201
    data = response.json()

    # Validate returned schema
    assert data["source_type"] == "image"
    assert data["detector_name"] == "dummy"
    assert "id" in data
    assert data["total_count"] >= 0
    assert "file_path" in data
    assert data["results"]["image_width"] == 200
    assert data["results"]["image_height"] == 150
    assert data["results"]["detector_name"] == "dummy"
    assert data["results"]["extra"] == {"note": "placeholder detections, not real"}

    # Verify database persistence
    db_record = db_session.query(Detection).filter(Detection.id == data["id"]).first()
    assert db_record is not None
    assert db_record.user_id == user.id
    assert db_record.source_type == "image"
    assert db_record.file_path == data["file_path"]
    assert db_record.total_count == data["total_count"]

    # Verify saved file exists on disk
    saved_path = Path(data["file_path"])
    assert saved_path.exists(), f"File does not exist on disk: {saved_path}"
    assert saved_path.is_file()


def test_detect_image_rejects_text_file_disguised_as_image(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test that uploading a plain text file named photo.jpg returns HTTP 400."""
    headers = _auth_header(test_users["user1"])
    fake_content = b"This is not a real image header, just plain text."

    response = client.post(
        "/detect/image",
        headers=headers,
        files={"file": ("photo.jpg", fake_content, "image/jpeg")},
    )
    assert response.status_code == 400
    assert "undecodable" in response.json()["detail"].lower() or "corrupted" in response.json()["detail"].lower()


def test_detect_image_rejects_unsupported_content_type(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test that a PDF content type returns HTTP 415 Unsupported Media Type."""
    headers = _auth_header(test_users["user1"])
    pdf_content = b"%PDF-1.4 dummy pdf header content"

    response = client.post(
        "/detect/image",
        headers=headers,
        files={"file": ("document.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 415
    assert "unsupported media type" in response.json()["detail"].lower()


def test_detect_image_rejects_empty_file(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test that uploading an empty 0-byte file returns HTTP 400 Bad Request."""
    headers = _auth_header(test_users["user1"])

    response = client.post(
        "/detect/image",
        headers=headers,
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_detect_image_rejects_oversized_file(
    client: TestClient,
    test_users: dict[str, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that exceeding MAX_UPLOAD_MB aborts streaming with HTTP 413."""
    headers = _auth_header(test_users["user1"])
    settings = get_settings()

    # Set limit to 0 MB so any non-empty upload triggers immediate 413 cutoff
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)

    img_bytes = _generate_image_bytes()
    response = client.post(
        "/detect/image",
        headers=headers,
        files={"file": ("toolarge.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed upload limit" in response.json()["detail"].lower()


def test_detect_image_sanitizes_path_traversal_filename(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test that '../../evil.jpg' is saved under a UUID name without client filename in path."""
    headers = _auth_header(test_users["user1"])
    img_bytes = _generate_image_bytes(format="JPEG")

    response = client.post(
        "/detect/image",
        headers=headers,
        files={"file": ("../../evil.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 201
    saved_path = response.json()["file_path"]

    # Verify neither 'evil' nor '..' is in the path
    assert "evil" not in saved_path
    assert ".." not in saved_path
    assert saved_path.endswith(".jpg")

    # Verify saved file exists on disk inside upload directory
    assert Path(saved_path).exists()


def test_detect_image_returns_503_when_detector_unavailable(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test that POST /detect/image returns 503 when app.state.detector is None."""
    headers = _auth_header(test_users["user1"])
    img_bytes = _generate_image_bytes()

    # Set app.state.detector to None
    original_detector = client.app.state.detector
    client.app.state.detector = None

    try:
        response = client.post(
            "/detect/image",
            headers=headers,
            files={"file": ("photo.jpg", img_bytes, "image/jpeg")},
        )
        assert response.status_code == 503
        assert "detector not available" in response.json()["detail"].lower()
    finally:
        client.app.state.detector = original_detector


# ==============================================================================
# GET /detect/history and GET /detect/{id} Tests
# ==============================================================================

def test_detect_history_and_item_access_control(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test user isolation in history and single-item retrieval, and admin access."""
    user1 = test_users["user1"]
    user2 = test_users["user2"]
    admin = test_users["admin"]

    img_bytes = _generate_image_bytes()

    # User 1 performs detection
    res1 = client.post(
        "/detect/image",
        headers=_auth_header(user1),
        files={"file": ("u1.jpg", img_bytes, "image/jpeg")},
    )
    assert res1.status_code == 201
    det1_id = res1.json()["id"]

    # User 2 performs detection
    res2 = client.post(
        "/detect/image",
        headers=_auth_header(user2),
        files={"file": ("u2.jpg", img_bytes, "image/jpeg")},
    )
    assert res2.status_code == 201
    det2_id = res2.json()["id"]

    # 1. User 1 history shows only user 1's detection
    history_u1 = client.get("/detect/history", headers=_auth_header(user1))
    assert history_u1.status_code == 200
    u1_items = history_u1.json()
    u1_ids = [item["id"] for item in u1_items]
    assert det1_id in u1_ids
    assert det2_id not in u1_ids

    # 2. User 2 history shows only user 2's detection
    history_u2 = client.get("/detect/history", headers=_auth_header(user2))
    assert history_u2.status_code == 200
    u2_items = history_u2.json()
    u2_ids = [item["id"] for item in u2_items]
    assert det2_id in u2_ids
    assert det1_id not in u2_ids

    # 3. User 1 cannot access User 2's detection by ID (returns 404, not revealing it exists)
    resp_cross = client.get(f"/detect/{det2_id}", headers=_auth_header(user1))
    assert resp_cross.status_code == 404
    assert "not found" in resp_cross.json()["detail"].lower()

    # User 1 can access own detection by ID
    resp_own = client.get(f"/detect/{det1_id}", headers=_auth_header(user1))
    assert resp_own.status_code == 200
    assert resp_own.json()["id"] == det1_id

    # 4. Admin can view everyone's detections in history
    history_admin = client.get("/detect/history", headers=_auth_header(admin))
    assert history_admin.status_code == 200
    admin_items = history_admin.json()
    admin_ids = [item["id"] for item in admin_items]
    assert det1_id in admin_ids
    assert det2_id in admin_ids

    # Admin can view User 1's detection by ID
    admin_get_det1 = client.get(f"/detect/{det1_id}", headers=_auth_header(admin))
    assert admin_get_det1.status_code == 200
    assert admin_get_det1.json()["id"] == det1_id

    # Admin can view User 2's detection by ID
    admin_get_det2 = client.get(f"/detect/{det2_id}", headers=_auth_header(admin))
    assert admin_get_det2.status_code == 200
    assert admin_get_det2.json()["id"] == det2_id


def test_event_loop_unblocked_during_image_upload(
    test_users: dict[str, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that event loop stays responsive during image upload by verifying concurrent /health returns quickly."""
    import asyncio
    import time
    import httpx
    from app.main import create_app
    from app.services.detector.factory import get_detector
    import app.api.routes.detect as detect_module

    app = create_app()
    detector = get_detector()
    detector.load()
    app.state.detector = detector

    user1 = test_users["user1"]
    token = create_access_token(user1.id)
    headers = {"Authorization": f"Bearer {token}"}

    orig_validate = detect_module.validate_and_save_image

    def slow_validate_and_save(file, settings):
        time.sleep(0.35)
        return orig_validate(file, settings=settings)

    monkeypatch.setattr(detect_module, "validate_and_save_image", slow_validate_and_save)

    img_bytes = _generate_image_bytes()

    async def run_concurrent_test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
            upload_completed = False

            async def do_upload():
                nonlocal upload_completed
                files = {"file": ("test.jpg", img_bytes, "image/jpeg")}
                res = await async_client.post("/detect/image", headers=headers, files=files)
                upload_completed = True
                return res

            async def do_health_probe():
                await asyncio.sleep(0.05)
                # Upload should still be executing in the worker threadpool
                assert not upload_completed
                t0 = time.perf_counter()
                res = await async_client.get("/health")
                t1 = time.perf_counter()
                duration = t1 - t0
                return res, duration

            upload_res, (health_res, health_duration) = await asyncio.gather(
                do_upload(),
                do_health_probe(),
            )
            return upload_res, health_res, health_duration

    upload_res, health_res, health_duration = asyncio.run(run_concurrent_test())

    assert upload_res.status_code == 201
    assert health_res.status_code == 200
    # If the event loop had been blocked by slow_validate_and_save (0.35s), health_duration would be >= 0.3s
    assert health_duration < 0.2


def test_detect_image_threadpool_http_exception_and_orphan_cleanup(
    client: TestClient,
    test_users: dict[str, User],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test that HTTPException raised in threadpool preserves status and detail, and orphan file is cleaned up."""
    user1 = test_users["user1"]
    token = create_access_token(user1.id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Verify HTTPException mapping from threadpool
    from fastapi import HTTPException, status
    import app.api.routes.detect as detect_module

    def raising_validate(file, settings):
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Custom upload limit exceeded",
        )

    monkeypatch.setattr(detect_module, "validate_and_save_image", raising_validate)

    img_bytes = _generate_image_bytes()
    res = client.post(
        "/detect/image",
        headers=headers,
        files={"file": ("test.jpg", img_bytes, "image/jpeg")},
    )
    assert res.status_code == 413
    assert res.json()["detail"] == "Custom upload limit exceeded"

    # 2. Verify orphan cleanup when failure occurs after validate_and_save_image returns a file_path
    dummy_file = tmp_path / "orphan_test.jpg"
    dummy_file.write_bytes(img_bytes)
    assert dummy_file.exists()

    def mock_validate_with_file(file, settings):
        return Image.new("RGB", (10, 10)), str(dummy_file)

    monkeypatch.setattr(detect_module, "validate_and_save_image", mock_validate_with_file)

    async def broken_inference(*args, **kwargs):
        raise RuntimeError("Inference exploded")

    monkeypatch.setattr("app.api.routes.detect.run_inference", broken_inference)

    res2 = client.post(
        "/detect/image",
        headers=headers,
        files={"file": ("test.jpg", img_bytes, "image/jpeg")},
    )
    assert res2.status_code == 500
    assert not dummy_file.exists(), "Orphan file must be cleaned up on inference failure"


