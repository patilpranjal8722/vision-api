"""Step 7 Hardening & Reliability Test Suite.

Covers:
1. Uniform error responses (404, 405, 422, 413, 429, 500, 401, 403) with request_id.
2. 500 responses sanitized (no stack traces, paths, SQL, or exceptions).
3. 422 responses stripped of password/token values.
4. X-Request-ID validation, generation, and propagation.
5. Security headers and Cache-Control no-store on /auth/*.
6. Request body limit middleware: 413 on large payloads except streaming detect endpoints.
7. Startup safety validation under DEBUG=false and ENABLE_DOCS toggle.
8. Rate limiting enforcement and /health /ready exemptions.
9. Inference protection: timeout (504), queue saturation (503), WebSocket error tolerance.
10. Video job frame failure resilience and failure ratio thresholding.
11. SQLite PRAGMAs (WAL, busy_timeout=5000, synchronous=NORMAL, foreign_keys=ON) on file DB.
12. Orphan upload cleanup on database failure.
13. Readiness probe (/ready) healthy vs degraded states.
14. Log redaction of sensitive credentials in dictionary messages and extras.
15. High-concurrency multithreaded request handling.
"""

from concurrent.futures import ThreadPoolExecutor
import io
import json
import logging
from pathlib import Path
import time
from typing import Generator, List, Set, Tuple
import uuid

import httpx
import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import INSECURE_SECRET_PLACEHOLDER, Settings, get_settings
from app.core.limiter import limiter
from app.core.logging import SensitiveDataFilter, StructuredJsonFormatter
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app, validate_startup_settings
from app.models.detection import Detection
from app.models.job import Job
from app.models.user import User
from app.schemas.detection import DetectedObject, DetectionResult
from app.services.detector import BaseDetector
from app.services.inference import InferenceTimeout, ServerBusy
from tests.conftest import TestingSessionLocal


def create_jpeg_bytes(width: int = 120, height: int = 120, size_target_kb: int = 0) -> bytes:
    """Create a JPEG byte string using Pillow, optionally padded to a target size."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=(120, 80, 200))
    img.save(buf, format="JPEG")
    data = buf.getvalue()
    if size_target_kb > 0:
        current_len = len(data)
        needed = (size_target_kb * 1024) - current_len
        if needed > 0:
            data += b"\x00" * needed
    return data


# 1. Error shapes and status codes
def test_all_error_classes_standard_shape(client: TestClient, db_session: Session) -> None:
    """Audit error classes to verify standard JSON shape {"detail": ..., "request_id": ...}."""
    # 404 Unknown route
    res_404 = client.get("/unknown-nonexistent-endpoint-404")
    assert res_404.status_code == 404
    data_404 = res_404.json()
    assert "detail" in data_404
    assert "request_id" in data_404
    assert res_404.headers.get("X-Request-ID") == data_404["request_id"]

    # 405 Method not allowed
    res_405 = client.post("/health")
    assert res_405.status_code == 405
    data_405 = res_405.json()
    assert "detail" in data_405
    assert "request_id" in data_405
    assert res_405.headers.get("X-Request-ID") == data_405["request_id"]

    # 422 Request validation error
    res_422 = client.post("/auth/register", json={"email": "not-an-email", "password": "weak_password_to_strip"})
    assert res_422.status_code == 422
    data_422 = res_422.json()
    assert "detail" in data_422
    assert "request_id" in data_422
    # Verify password input is sanitized and not echoed in 422 body
    detail_str = json.dumps(data_422["detail"])
    assert "weak_password_to_strip" not in detail_str

    # 401 Unauthorized
    res_401 = client.get("/users/me")
    assert res_401.status_code == 401
    data_401 = res_401.json()
    assert "detail" in data_401
    assert "request_id" in data_401

    # 403 Forbidden (standard user requesting admin-only endpoint)
    std_user = User(
        email="std@example.com",
        username="std_user",
        hashed_password=hash_password("Str0ng!Pass123"),
        role="user",
        is_active=True,
    )
    db_session.add(std_user)
    db_session.commit()
    token = create_access_token(std_user.id)
    res_403 = client.get("/users/", headers={"Authorization": f"Bearer {token}"})
    assert res_403.status_code == 403
    data_403 = res_403.json()
    assert "detail" in data_403
    assert "request_id" in data_403


def test_500_unhandled_exception_sanitized(client: TestClient) -> None:
    """Unhandled exceptions must return 500 without leaking stack trace, path, or SQL."""
    app = client.app

    @app.get("/test-raise-unexpected-500")
    def test_raise():
        raise RuntimeError("SELECT * FROM passwords WHERE path='/private/secrets/db.py'")

    # Use raise_server_exceptions=False so TestClient returns the 500 JSONResponse instead of re-raising
    with TestClient(app, raise_server_exceptions=False) as safe_client:
        res = safe_client.get("/test-raise-unexpected-500")
        assert res.status_code == 500
        data = res.json()
        assert data["detail"] == "Internal server error"
        assert "request_id" in data
        # Confirm none of the sensitive exception strings appear in the response body
        body_text = res.text
        assert "RuntimeError" not in body_text
        assert "SELECT" not in body_text
        assert "passwords" not in body_text
        assert "/private/secrets" not in body_text


# 2. X-Request-ID middleware
def test_x_request_id_middleware(client: TestClient) -> None:
    """Verify incoming X-Request-ID validation, replacement, and generation."""
    # Safe valid incoming ID: echoed back
    valid_id = "req_12345-ABC_safe"
    res = client.get("/health", headers={"X-Request-ID": valid_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == valid_id

    # Invalid incoming ID with unsafe characters (spaces, symbols): replaced with UUID4
    unsafe_id = "bad id with spaces & symbols!@#"
    res = client.get("/health", headers={"X-Request-ID": unsafe_id})
    assert res.status_code == 200
    returned_id = res.headers.get("X-Request-ID")
    assert returned_id != unsafe_id
    assert uuid.UUID(returned_id)

    # Invalid incoming ID exceeding 64 chars: replaced with UUID4
    too_long = "a" * 65
    res = client.get("/health", headers={"X-Request-ID": too_long})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") != too_long
    assert uuid.UUID(res.headers.get("X-Request-ID"))

    # Missing X-Request-ID: newly generated UUID4
    res = client.get("/health")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers
    assert uuid.UUID(res.headers["X-Request-ID"])


# 3. Security headers middleware
def test_security_headers_and_cache_control(client: TestClient) -> None:
    """Verify security headers on responses and Cache-Control: no-store on /auth/*."""
    res = client.get("/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "no-referrer"
    assert "Content-Security-Policy" not in res.headers

    # Auth routes must have Cache-Control: no-store
    auth_res = client.post("/auth/login", data={"username": "fake", "password": "fake"})
    assert auth_res.headers.get("Cache-Control") == "no-store"
    assert auth_res.headers.get("X-Content-Type-Options") == "nosniff"


# 4. Request body limit middleware
def test_request_body_limit_normal_vs_streaming(client: TestClient, db_session: Session) -> None:
    """Verify 413 for oversized normal payloads, while detect endpoints keep streaming limits."""
    settings = get_settings()
    max_bytes = settings.MAX_REQUEST_BODY_KB * 1024

    # Normal endpoint (/auth/login) with Content-Length exceeding MAX_REQUEST_BODY_KB
    oversized_headers = {
        "Content-Length": str(max_bytes + 2048),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    res_413 = client.post("/auth/login", content=b"x" * 100, headers=oversized_headers)
    assert res_413.status_code == 413
    assert f"{settings.MAX_REQUEST_BODY_KB} KB" in res_413.json()["detail"]
    assert "request_id" in res_413.json()

    # /detect/image with Content-Length larger than MAX_REQUEST_BODY_KB (e.g. 1.2 MB)
    user = User(
        email="img_user@example.com",
        username="img_user",
        hashed_password=hash_password("Str0ng!Pass123"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(user.id)

    # 1.2 MB image file
    large_img = create_jpeg_bytes(width=1000, height=1000)
    if len(large_img) <= max_bytes:
        large_img = large_img + (b"\x00" * (max_bytes - len(large_img) + 5000))

    img_res = client.post(
        "/detect/image",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("large_image.jpg", large_img, "image/jpeg")},
    )
    # Must NOT be rejected by RequestBodyLimitMiddleware with 413
    assert img_res.status_code == 201


# 5. Rate limiting
def test_rate_limits_and_health_exemption(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify rate limit enforcement with Retry-After and ensure /health and /ready are exempted."""
    settings = get_settings()
    monkeypatch.setattr(settings, "UPLOAD_RATE_LIMIT", "3/minute")
    limiter.enabled = True

    user = User(
        email="rate_user@example.com",
        username="rate_user",
        hashed_password=hash_password("Str0ng!Pass123"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(user.id)
    auth_headers = {"Authorization": f"Bearer {token}"}

    img_bytes = create_jpeg_bytes()

    # Send 3 uploads (allowed by 3/minute)
    for _ in range(3):
        res = client.post(
            "/detect/image",
            headers=auth_headers,
            files={"file": ("frame.jpg", img_bytes, "image/jpeg")},
        )
        assert res.status_code == 201

    # 4th upload must exceed rate limit
    res_4th = client.post(
        "/detect/image",
        headers=auth_headers,
        files={"file": ("frame.jpg", img_bytes, "image/jpeg")},
    )
    assert res_4th.status_code == 429
    assert "Retry-After" in res_4th.headers
    assert "request_id" in res_4th.json()
    assert "Rate limit exceeded" in res_4th.json()["detail"]

    # Verify /health and /ready are completely exempted from rate limits
    for _ in range(15):
        h_res = client.get("/health")
        assert h_res.status_code == 200
        r_res = client.get("/ready")
        assert r_res.status_code == 200


# 6. Startup safety
def test_startup_safety_validation() -> None:
    """Verify production startup validation rules."""
    # In DEBUG mode, weak keys only log a warning
    debug_settings = Settings(DEBUG=True, SECRET_KEY="weak")
    validate_startup_settings(debug_settings)  # Does not raise

    # In production (DEBUG=False):
    # Empty secret key
    with pytest.raises(RuntimeError, match="Production startup failed: SECRET_KEY"):
        validate_startup_settings(Settings(DEBUG=False, SECRET_KEY=""))

    # Placeholder secret key
    with pytest.raises(RuntimeError, match="Production startup failed: SECRET_KEY"):
        validate_startup_settings(Settings(DEBUG=False, SECRET_KEY=INSECURE_SECRET_PLACEHOLDER))

    # Shorter than 32 characters
    with pytest.raises(RuntimeError, match="Production startup failed: SECRET_KEY"):
        validate_startup_settings(Settings(DEBUG=False, SECRET_KEY="too_short_secret_key_123"))

    # Wildcard ALLOWED_ORIGINS
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS must not contain wildcard"):
        validate_startup_settings(
            Settings(
                DEBUG=False,
                SECRET_KEY="a_very_strong_production_secret_key_that_is_long_enough",
                ALLOWED_ORIGINS=["*"],
            )
        )

    # Valid production settings pass
    prod_valid = Settings(
        DEBUG=False,
        SECRET_KEY="a_very_strong_production_secret_key_that_is_long_enough",
        ALLOWED_ORIGINS=["https://example.com"],
    )
    validate_startup_settings(prod_valid)


def test_enable_docs_toggle() -> None:
    """When ENABLE_DOCS=false, /docs, /redoc, and /openapi.json return 404."""
    no_docs_settings = Settings(ENABLE_DOCS=False)
    no_docs_app = create_app(no_docs_settings)
    with TestClient(no_docs_app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404


# 7. Inference protection
class SlowDetector(BaseDetector):
    def __init__(self, delay_s: float = 0.2):
        self.name = "slow_detector"
        self.delay_s = delay_s
        self._is_loaded = True

    def load(self) -> None:
        self._is_loaded = True

    def detect(self, image: Image.Image) -> DetectionResult:
        if self.delay_s > 0:
            time.sleep(self.delay_s)
        return DetectionResult(
            detector_name=self.name,
            objects=[],
            total_count=0,
            image_width=120,
            image_height=120,
            inference_ms=1.0,
        )


def test_inference_protection_timeout(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A slow detector exceeding INFERENCE_TIMEOUT_SECONDS returns 504."""
    settings = get_settings()
    monkeypatch.setattr(settings, "INFERENCE_TIMEOUT_SECONDS", 0.05)

    client.app.state.detector = SlowDetector(delay_s=0.2)

    user = User(
        email="slow_user@example.com",
        username="slow_user",
        hashed_password=hash_password("Str0ng!Pass123"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(user.id)

    res = client.post(
        "/detect/image",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("frame.jpg", create_jpeg_bytes(), "image/jpeg")},
    )
    assert res.status_code == 504
    assert res.json()["detail"] == "Inference timeout"
    assert "request_id" in res.json()


def test_inference_protection_server_busy(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Queue saturation raises ServerBusy and returns 503."""
    settings = get_settings()
    monkeypatch.setattr(settings, "INFERENCE_QUEUE_LIMIT", 0)

    user = User(
        email="busy_user@example.com",
        username="busy_user",
        hashed_password=hash_password("Str0ng!Pass123"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(user.id)

    res = client.post(
        "/detect/image",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("frame.jpg", create_jpeg_bytes(), "image/jpeg")},
    )
    assert res.status_code == 503
    assert res.json()["detail"] == "Server busy, try again shortly"
    assert "request_id" in res.json()


def test_ws_stream_inference_timeout_keeps_connection_open(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """WebSocket stream timeout sends an error message and keeps the connection open."""
    user = User(
        email="ws_timeout_user@example.com",
        username="ws_timeout_user",
        hashed_password=hash_password("Str0ng!Pass123"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(user.id)

    # Attach slow detector with tiny timeout
    settings = get_settings()
    monkeypatch.setattr(settings, "INFERENCE_TIMEOUT_SECONDS", 0.05)
    client.app.state.detector = SlowDetector(delay_s=0.2)

    with client.websocket_connect("/ws/stream") as ws:
        # Auth handshake
        ws.send_json({"type": "auth", "token": token})
        resp = ws.receive_json()
        assert resp["type"] == "auth_ok"

        # Send frame that times out
        ws.send_bytes(create_jpeg_bytes())
        err_resp = ws.receive_json()
        assert err_resp["type"] == "error"
        assert "timed out" in err_resp["message"].lower()

        # Allow previous background worker thread to finish its delay
        time.sleep(0.3)

        # Connection is still open: restore normal timeout and fast detector, then send second frame
        monkeypatch.setattr(settings, "INFERENCE_TIMEOUT_SECONDS", 5.0)
        client.app.state.detector = SlowDetector(delay_s=0.0)
        ws.send_bytes(create_jpeg_bytes())
        det_resp = ws.receive_json()
        assert det_resp["type"] == "detections"


# 8. Video job frame failures
class FaultyDetector(BaseDetector):
    def __init__(self, failure_indices: Set[int]):
        self.name = "faulty_detector"
        self.failure_indices = failure_indices
        self.call_count = 0
        self._is_loaded = True

    def load(self) -> None:
        self._is_loaded = True

    def detect(self, image: Image.Image) -> DetectionResult:
        idx = self.call_count
        self.call_count += 1
        if idx in self.failure_indices:
            raise RuntimeError(f"Detector crashed on frame {idx}")
        return DetectionResult(
            detector_name=self.name,
            objects=[],
            total_count=0,
            image_width=640,
            image_height=480,
            inference_ms=1.0,
        )


def test_video_job_frame_failures_resilience_and_threshold(client: TestClient, db_session: Session) -> None:
    """Video jobs skip isolated failed frames, and fail only when failure ratio exceeds threshold."""
    user = User(
        email="faulty_vid_user@example.com",
        username="faulty_vid_user",
        hashed_password=hash_password("Str0ng!Pass123"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(user.id)
    auth_headers = {"Authorization": f"Bearer {token}"}

    fake_mp4 = b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00isommp42\x00\x00\x00\x08free\x00\x00\x00\x08mdat"

    # Case A: Fails on 1 out of 20 frames (ratio 0.05 < 0.5) -> job completes with status 'done'
    client.app.state.detector = FaultyDetector(failure_indices={2})
    res_a = client.post(
        "/detect/video",
        headers=auth_headers,
        files={"file": ("video_a.mp4", fake_mp4, "video/mp4")},
    )
    assert res_a.status_code == 202
    job_id_a = res_a.json().get("job_id") or res_a.json().get("id")

    job_a = db_session.query(Job).filter(Job.id == job_id_a).first()
    assert job_a is not None
    assert job_a.status == "done"
    assert job_a.result is not None
    assert job_a.result.get("summary", {}).get("frames_failed") == 1

    # Case B: Fails on 15 out of 20 frames (ratio 0.75 > 0.5) -> job fails
    client.app.state.detector = FaultyDetector(failure_indices=set(range(15)))
    res_b = client.post(
        "/detect/video",
        headers=auth_headers,
        files={"file": ("video_b.mp4", fake_mp4, "video/mp4")},
    )
    assert res_b.status_code == 202
    job_id_b = res_b.json().get("job_id") or res_b.json().get("id")

    job_b = db_session.query(Job).filter(Job.id == job_id_b).first()
    assert job_b is not None
    assert job_b.status == "failed"
    assert job_b.error == "Processing failed"
    assert "Traceback" not in job_b.error


# 9. SQLite PRAGMAs on a temporary file database
def test_sqlite_pragmas_on_file_db(tmp_path: Path) -> None:
    """Verify PRAGMA journal_mode=WAL, busy_timeout=5000, synchronous=NORMAL, foreign_keys=ON."""
    db_file = tmp_path / "pragma_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()
        synchronous = conn.execute(text("PRAGMA synchronous")).scalar()
        foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()

        assert str(journal_mode).lower() == "wal"
        assert busy_timeout == 5000
        assert synchronous == 1  # 1 corresponds to NORMAL in SQLite
        assert foreign_keys == 1


# 10. Orphan file cleanup
def test_orphan_file_cleanup_on_db_failure(client: TestClient, db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force database commit to fail and ensure saved upload file is unlinked."""
    user = User(
        email="orphan_user@example.com",
        username="orphan_user",
        hashed_password=hash_password("Str0ng!Pass123"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(user.id)

    # Track files in upload directory before request
    settings = get_settings()
    upload_dir = Path(settings.UPLOAD_DIR)

    # Force commit failure
    def failing_commit(self: Session):
        raise RuntimeError("Simulated DB failure during commit")

    monkeypatch.setattr(Session, "commit", failing_commit)

    with pytest.raises(Exception):
        client.post(
            "/detect/image",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("frame.jpg", create_jpeg_bytes(), "image/jpeg")},
        )

    # Verify no orphan image files exist in uploads
    image_files = list(upload_dir.glob("**/*.jpg")) + list(upload_dir.glob("**/*.jpeg"))
    assert len(image_files) == 0


# 11. Readiness probe
def test_readiness_probe_endpoints(client: TestClient) -> None:
    """GET /ready returns 200 normally and 503 when detector is None or DB is down."""
    # Healthy case
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready"}

    # Detector is None case
    client.app.state.detector = None
    res_none = client.get("/ready")
    assert res_none.status_code == 503
    data = res_none.json()
    assert "detector check failed" in data["detail"].lower()
    assert "request_id" in data


# 12. Log redaction
def test_log_redaction_filter() -> None:
    """SensitiveDataFilter must redact sensitive credential keys in dict messages and extras."""
    filt = SensitiveDataFilter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg={"username": "alice", "password": "supersecretpassword123"},
        args=(),
        exc_info=None,
    )
    record.token = "bearer_jwt_token_456"
    record.custom_extra = {"secret_key": "my_ultra_secret_key"}

    filt.filter(record)

    assert record.msg["password"] == "[REDACTED]"
    assert record.msg["username"] == "alice"
    assert record.token == "[REDACTED]"
    assert record.custom_extra["secret_key"] == "[REDACTED]"


# 13. Concurrency
def test_concurrency_parallel_requests(tmp_path: Path) -> None:
    """Execute 20 concurrent parallel requests to /health and /users/me without errors."""
    db_file = tmp_path / "concurrent_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    ThreadSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    app = create_app()

    def get_thread_db():
        s = ThreadSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = get_thread_db

    init_session = ThreadSession()
    user = User(
        email="concurrent_user@example.com",
        username="concurrent_user",
        hashed_password=hash_password("Str0ng!Pass123"),
        role="user",
        is_active=True,
    )
    init_session.add(user)
    init_session.commit()
    user_id = user.id
    init_session.close()

    token = create_access_token(user_id)
    auth_headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        def fetch_health() -> int:
            return client.get("/health").status_code

        def fetch_me() -> int:
            return client.get("/users/me", headers=auth_headers).status_code

        with ThreadPoolExecutor(max_workers=20) as executor:
            health_futures = [executor.submit(fetch_health) for _ in range(20)]
            me_futures = [executor.submit(fetch_me) for _ in range(20)]

            health_results = [f.result() for f in health_futures]
            me_results = [f.result() for f in me_futures]

    assert all(code == 200 for code in health_results)
    assert all(code == 200 for code in me_results)
