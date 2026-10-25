"""Comprehensive integration tests for video detection jobs and job status management."""

import io
from pathlib import Path
import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models.detection import Detection
from app.models.job import Job
from app.models.user import User
from app.services.job_runner import reconcile_stale_jobs

# Valid MP4 dummy container bytes for testing
VALID_MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 2048)


@pytest.fixture
def test_users(db_session: Session) -> dict[str, User]:
    """Create test users (two standard users and one admin user)."""
    user1 = User(
        email="alice_video@example.com",
        username="alice_video",
        hashed_password=hash_password("password123"),
        role="user",
        is_active=True,
    )
    user2 = User(
        email="bob_video@example.com",
        username="bob_video",
        hashed_password=hash_password("password123"),
        role="user",
        is_active=True,
    )
    admin = User(
        email="admin_video@example.com",
        username="admin_video",
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
    """Return Authorization Bearer header for a given user."""
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. POST /detect/video Upload & Validation Tests
# ==============================================================================

def test_detect_video_requires_authentication(client: TestClient) -> None:
    """Test that POST /detect/video returns HTTP 401 without Bearer token."""
    response = client.post(
        "/detect/video",
        files={"file": ("test.mp4", VALID_MP4_BYTES, "video/mp4")},
    )
    assert response.status_code == 401


def test_detect_video_rejects_empty_file(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test that uploading a 0-byte video returns HTTP 400 Bad Request."""
    headers = _auth_header(test_users["user1"])
    response = client.post(
        "/detect/video",
        headers=headers,
        files={"file": ("empty.mp4", b"", "video/mp4")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_detect_video_rejects_unsupported_content_type(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test that invalid MIME type (e.g. application/pdf) returns HTTP 415."""
    headers = _auth_header(test_users["user1"])
    response = client.post(
        "/detect/video",
        headers=headers,
        files={"file": ("file.pdf", b"%PDF-1.4 dummy", "application/pdf")},
    )
    assert response.status_code == 415
    assert "unsupported media type" in response.json()["detail"].lower()


def test_detect_video_rejects_oversized_file(
    client: TestClient,
    test_users: dict[str, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that exceeding MAX_VIDEO_UPLOAD_MB aborts streaming with HTTP 413."""
    headers = _auth_header(test_users["user1"])
    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_VIDEO_UPLOAD_MB", 0)

    response = client.post(
        "/detect/video",
        headers=headers,
        files={"file": ("toolarge.mp4", VALID_MP4_BYTES, "video/mp4")},
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed upload limit" in response.json()["detail"].lower()


def test_detect_video_validates_frame_skip_range(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test that frame_skip values outside 1..60 return HTTP 422 Unprocessable Entity."""
    headers = _auth_header(test_users["user1"])

    # frame_skip=0 (below minimum 1)
    res_zero = client.post(
        "/detect/video?frame_skip=0",
        headers=headers,
        files={"file": ("video.mp4", VALID_MP4_BYTES, "video/mp4")},
    )
    assert res_zero.status_code == 422

    # frame_skip=999 (above maximum 60)
    res_999 = client.post(
        "/detect/video?frame_skip=999",
        headers=headers,
        files={"file": ("video.mp4", VALID_MP4_BYTES, "video/mp4")},
    )
    assert res_999.status_code == 422


def test_detect_video_success_and_path_sanitization(
    client: TestClient,
    test_users: dict[str, User],
    db_session: Session,
) -> None:
    """Test successful submission: returns 202 with job_id, saves with UUID filename."""
    headers = _auth_header(test_users["user1"])

    response = client.post(
        "/detect/video?frame_skip=5",
        headers=headers,
        files={"file": ("../../evil.mp4", VALID_MP4_BYTES, "video/mp4")},
    )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ["pending", "done"]  # inline execution finishes immediately
    job_id = data["job_id"]

    # Verify Job row in database
    job = db_session.query(Job).filter(Job.id == job_id).first()
    assert job is not None
    assert "evil" not in job.input_path
    assert ".." not in job.input_path
    assert job.input_path.endswith(".mp4")
    assert Path(job.input_path).exists()


def test_detect_video_returns_503_when_detector_none(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test that POST /detect/video returns 503 when app.state.detector is None."""
    headers = _auth_header(test_users["user1"])
    original_detector = client.app.state.detector
    client.app.state.detector = None

    try:
        response = client.post(
            "/detect/video",
            headers=headers,
            files={"file": ("video.mp4", VALID_MP4_BYTES, "video/mp4")},
        )
        assert response.status_code == 503
        assert "detector not available" in response.json()["detail"].lower()
    finally:
        client.app.state.detector = original_detector


# ==============================================================================
# 2. Job Lifecycle & Detection Verification Tests
# ==============================================================================

def test_job_lifecycle_complete_result_and_detection_row(
    client: TestClient,
    test_users: dict[str, User],
    db_session: Session,
) -> None:
    """Verify that completed job has progress 100, summary, timeline, and a Detection row."""
    headers = _auth_header(test_users["user1"])

    # In conftest, JOB_RUNNER_INLINE is True by default
    submit_res = client.post(
        "/detect/video?frame_skip=5",
        headers=headers,
        files={"file": ("clip.mp4", VALID_MP4_BYTES, "video/mp4")},
    )
    assert submit_res.status_code == 202
    job_id = submit_res.json()["job_id"]

    # Inspect job status
    get_res = client.get(f"/jobs/{job_id}", headers=headers)
    assert get_res.status_code == 200
    job_data = get_res.json()
    assert job_data["status"] == "done"
    assert job_data["progress"] == 100
    assert job_data["error"] is None

    result = job_data["result"]
    assert result is not None
    assert "summary" in result
    assert "timeline" in result
    assert "peak_frame" in result

    summary = result["summary"]
    assert summary["frames_total"] >= 60
    assert summary["frames_processed"] > 0
    assert summary["frame_skip"] == 5
    assert summary["fps"] == 25.0
    assert summary["detector_name"] == "dummy"

    peak_frame = result["peak_frame"]
    assert "frame_index" in peak_frame
    assert "total_count" in peak_frame
    assert "objects" in peak_frame

    # Verify a Detection row exists linked to this job_id
    detection = db_session.query(Detection).filter(Detection.job_id == job_id).first()
    assert detection is not None
    assert detection.source_type == "video"
    assert detection.user_id == test_users["user1"].id
    assert detection.total_count == peak_frame["total_count"]
    assert detection.detector_name == "dummy"


def test_async_job_runner_with_polling(
    test_users: dict[str, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test asynchronous background execution with ThreadPoolExecutor and status polling."""
    settings = get_settings()
    # Explicitly enable multi-threaded async job execution
    monkeypatch.setattr(settings, "JOB_RUNNER_INLINE", False)
    monkeypatch.setattr(settings, "DUMMY_FRAME_DELAY_MS", 2)

    app = create_app()
    with TestClient(app) as test_client:
        headers = _auth_header(test_users["user1"])
        submit_res = test_client.post(
            "/detect/video?frame_skip=10",
            headers=headers,
            files={"file": ("async.mp4", VALID_MP4_BYTES, "video/mp4")},
        )
        assert submit_res.status_code == 202
        job_id = submit_res.json()["job_id"]

        # Poll until done (timeout 10s)
        start_time = time.time()
        final_status = None
        while time.time() - start_time < 10.0:
            res = test_client.get(f"/jobs/{job_id}", headers=headers)
            assert res.status_code == 200
            data = res.json()
            if data["status"] in ["done", "failed"]:
                final_status = data["status"]
                break
            time.sleep(0.1)

        assert final_status == "done"
        assert data["progress"] == 100
        assert data["result"] is not None


# ==============================================================================
# 3. Job Failure & Error Isolation Tests
# ==============================================================================

def test_job_failure_path_sanitized_error_and_server_health(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Test that frame reader exceptions mark job as 'failed' with sanitized message."""
    headers = _auth_header(test_users["user1"])

    # Simulate frame reader failing during execution
    with patch(
        "app.services.video.dummy.DummyFrameReader.iter_frames",
        side_effect=RuntimeError("Corrupt frame stream simulation"),
    ):
        res = client.post(
            "/detect/video",
            headers=headers,
            files={"file": ("corrupt.mp4", VALID_MP4_BYTES, "video/mp4")},
        )
        assert res.status_code == 202
        job_id = res.json()["job_id"]

    # Check job status is failed and error is sanitized
    job_res = client.get(f"/jobs/{job_id}", headers=headers)
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["status"] == "failed"
    assert job_data["error"] == "Processing failed"
    assert job_data["result"] is None

    # Server /health must still return ok
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    # Subsequent second job still succeeds normally
    res_second = client.post(
        "/detect/video",
        headers=headers,
        files={"file": ("normal.mp4", VALID_MP4_BYTES, "video/mp4")},
    )
    assert res_second.status_code == 202
    job2_id = res_second.json()["job_id"]
    job2_res = client.get(f"/jobs/{job2_id}", headers=headers)
    assert job2_res.status_code == 200
    assert job2_res.json()["status"] == "done"


# ==============================================================================
# 4. Access Control, Limits & Stale Reconciliation Tests
# ==============================================================================

def test_job_access_control_and_list_filtering(
    client: TestClient,
    test_users: dict[str, User],
) -> None:
    """Verify owner isolation, 404 for other users, admin access, and status filtering."""
    u1_headers = _auth_header(test_users["user1"])
    u2_headers = _auth_header(test_users["user2"])
    admin_headers = _auth_header(test_users["admin"])

    # User 1 submits a job
    res1 = client.post(
        "/detect/video",
        headers=u1_headers,
        files={"file": ("u1.mp4", VALID_MP4_BYTES, "video/mp4")},
    )
    job1_id = res1.json()["job_id"]

    # User 2 submits a job
    res2 = client.post(
        "/detect/video",
        headers=u2_headers,
        files={"file": ("u2.mp4", VALID_MP4_BYTES, "video/mp4")},
    )
    job2_id = res2.json()["job_id"]

    # User 2 receives 404 trying to access User 1's job
    res_unauthorized = client.get(f"/jobs/{job1_id}", headers=u2_headers)
    assert res_unauthorized.status_code == 404
    assert "job not found" in res_unauthorized.json()["detail"].lower()

    # User 1 can view own job
    res_own = client.get(f"/jobs/{job1_id}", headers=u1_headers)
    assert res_own.status_code == 200
    assert res_own.json()["id"] == job1_id

    # Admin can view User 1's job
    res_admin = client.get(f"/jobs/{job1_id}", headers=admin_headers)
    assert res_admin.status_code == 200
    assert res_admin.json()["id"] == job1_id

    # GET /jobs list: User 1 sees only job 1
    u1_list = client.get("/jobs", headers=u1_headers)
    assert u1_list.status_code == 200
    u1_job_ids = [j["id"] for j in u1_list.json()]
    assert job1_id in u1_job_ids
    assert job2_id not in u1_job_ids

    # Admin sees both jobs
    admin_list = client.get("/jobs", headers=admin_headers)
    assert admin_list.status_code == 200
    admin_job_ids = [j["id"] for j in admin_list.json()]
    assert job1_id in admin_job_ids
    assert job2_id in admin_job_ids

    # Status filter test
    filtered_list = client.get("/jobs?status=done", headers=u1_headers)
    assert filtered_list.status_code == 200
    for j in filtered_list.json():
        assert j["status"] == "done"


def test_max_active_jobs_per_user_limit(
    client: TestClient,
    test_users: dict[str, User],
    db_session: Session,
) -> None:
    """Test that exceeding MAX_ACTIVE_JOBS_PER_USER returns HTTP 429."""
    user1 = test_users["user1"]
    headers = _auth_header(user1)

    # Insert 3 active jobs directly into DB for User 1
    for i in range(3):
        job = Job(
            id=f"active-test-job-{i}",
            user_id=user1.id,
            type="video",
            status="pending",
            progress=0,
            input_path="/path/dummy.mp4",
        )
        db_session.add(job)
    db_session.commit()

    # Attempt to submit 4th job
    res = client.post(
        "/detect/video",
        headers=headers,
        files={"file": ("extra.mp4", VALID_MP4_BYTES, "video/mp4")},
    )
    assert res.status_code == 429
    assert "active job limit reached" in res.json()["detail"].lower()


def test_reconcile_stale_jobs_at_startup(
    db_session: Session,
) -> None:
    """Test that jobs left in 'pending' or 'running' status are marked failed."""
    user = User(
        email="reconcile_stale@example.com",
        username="reconcile_stale",
        hashed_password="password123",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    job_pending = Job(
        id="stale-pending-1",
        user_id=user.id,
        type="video",
        status="pending",
        progress=0,
        input_path="/tmp/test1.mp4",
    )
    job_running = Job(
        id="stale-running-2",
        user_id=user.id,
        type="video",
        status="running",
        progress=45,
        input_path="/tmp/test2.mp4",
    )
    db_session.add_all([job_pending, job_running])
    db_session.commit()

    reconciled_count = reconcile_stale_jobs()
    assert reconciled_count == 2

    db_session.refresh(job_pending)
    db_session.refresh(job_running)

    assert job_pending.status == "failed"
    assert job_pending.error == "Server restarted while the job was running"
    assert job_running.status == "failed"
    assert job_running.error == "Server restarted while the job was running"
