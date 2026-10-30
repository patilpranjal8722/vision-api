"""Comprehensive tests for CV microservice integration (BP-A1).

Covers:
1. Pydantic v2 schemas: event types, validation rules, timestamps, bbox, flags.
2. Service-to-service authentication: X-Service-Key, fail-closed, log redaction.
3. Event intake and idempotency: deduplication, batching, limits, 413, 422.
4. Job lifecycle mutations: progress monotonicity, terminal states, error sanitization.
5. Handler registry: dispatching, error resilience, outcome recording.
6. Startup security safety: DEBUG true/false key validation.
7. Database migration: table and column verification.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, List

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config
from app.core.config import Settings, get_settings
from app.core.logging import SensitiveDataFilter
from app.main import create_app, validate_startup_settings
from app.models.cv_event import CvEvent
from app.models.job import Job
from app.schemas.cv import (
    BoundingBoxPx,
    CameraStatusEvent,
    CvEventEnvelope,
    Identity,
    ItemStatus,
    Items,
    JobCompletedEvent,
    JobFailedEvent,
    JobProgressEvent,
    ViolationConfirmedEvent,
    ViolationEndedEvent,
    WorkerState,
    WorkerStatusEvent,
)
from app.services.cv_events import (
    clear_event_handlers,
    register_event_handler,
)

VALID_KEY = "test-cv-events-api-key-for-internal-testing-32b"
VALID_OUTBOUND_KEY = "test-cv-service-api-key-outbound-testing-32b"


@pytest.fixture(autouse=True)
def setup_cv_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure deterministic CV microservice keys for tests."""
    settings = get_settings()
    monkeypatch.setattr(settings, "CV_EVENTS_API_KEY", VALID_KEY)
    monkeypatch.setattr(settings, "CV_SERVICE_API_KEY", VALID_OUTBOUND_KEY)
    clear_event_handlers()


# ===========================================================================
# 1. Schema Unit Tests
# ===========================================================================

class TestCvSchemas:
    """Validate Pydantic v2 schemas for all CV event types and rules."""

    def test_valid_job_progress_event(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "job.progress",
            "occurred_at": "2026-10-31T12:00:00Z",
            "job_id": "cv-job-01",
            "sequence": 1,
            "data": {"progress": 45, "frames_processed": 300},
        }
        event = TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert isinstance(event, JobProgressEvent)
        assert event.data.progress == 45
        assert event.data.frames_processed == 300

    def test_valid_job_completed_event(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "job.completed",
            "occurred_at": "2026-10-31T12:05:00Z",
            "job_id": "cv-job-01",
            "data": {
                "summary": {
                    "workers_tracked": 10,
                    "compliant": 8,
                    "violations": 2,
                    "uncertain": 0,
                    "unidentified_workers": 1,
                    "violation_events": 2,
                    "compliance_rate": 0.8,
                }
            },
        }
        event = TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert isinstance(event, JobCompletedEvent)
        assert event.data.summary.compliance_rate == 0.8

    def test_valid_job_failed_event(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "job.failed",
            "occurred_at": "2026-10-31T12:01:00Z",
            "job_id": "cv-job-01",
            "data": {
                "error": {
                    "code": "DECODE_ERROR",
                    "message": "Corrupt stream packet",
                }
            },
        }
        event = TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert isinstance(event, JobFailedEvent)
        assert event.data.error.code == "DECODE_ERROR"

    def test_valid_worker_status_event(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "worker.status",
            "occurred_at": "2026-10-31T12:02:00Z",
            "job_id": "cv-job-01",
            "data": {
                "track_id": 101,
                "verdict": "compliant",
                "items": {
                    "helmet": {"status": "present", "confidence": 0.95},
                    "vest": {"status": "present", "confidence": 0.88},
                },
                "identity": {
                    "method": "ocr",
                    "code": "EMP-100",
                    "confidence": 0.90,
                    "verified": True,
                },
                "flags": ["low_light"],
                "why": ["Wearing required gear."],
                "bbox": {"x1": 10.0, "y1": 20.0, "x2": 150.0, "y2": 300.0},
            },
        }
        event = TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert isinstance(event, WorkerStatusEvent)
        assert event.data.identity is not None and event.data.identity.code == "EMP-100"

    def test_valid_violation_confirmed_event(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "violation.confirmed",
            "occurred_at": "2026-10-31T12:03:00Z",
            "job_id": "cv-job-01",
            "data": {
                "violation_key": "vkey-101-h",
                "track_id": 101,
                "missing_items": ["helmet"],
                "started_at": "2026-10-31T12:02:50Z",
                "started_s": 12.5,
                "ended_at": None,
                "why": ["No helmet on head."],
            },
        }
        event = TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert isinstance(event, ViolationConfirmedEvent)
        assert event.data.missing_items == ["helmet"]

    def test_valid_violation_ended_event(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "violation.ended",
            "occurred_at": "2026-10-31T12:03:30Z",
            "job_id": "cv-job-01",
            "data": {
                "violation_key": "vkey-101-h",
                "ended_at": "2026-10-31T12:03:30Z",
                "duration_s": 25.0,
            },
        }
        event = TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert isinstance(event, ViolationEndedEvent)
        assert event.data.duration_s == 25.0

    def test_valid_camera_status_event(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "camera.status",
            "occurred_at": "2026-10-31T12:00:00Z",
            "job_id": "cv-job-01",
            "data": {"state": "connected", "message": "Stream online"},
        }
        event = TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert isinstance(event, CameraStatusEvent)
        assert event.data.state == "connected"

    def test_naive_timestamp_rejected(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "job.progress",
            "occurred_at": "2026-10-31T12:00:00",  # No timezone
            "job_id": "cv-job-01",
            "data": {"progress": 10},
        }
        with pytest.raises(ValidationError) as exc_info:
            TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert "Timestamp must be timezone-aware" in str(exc_info.value)

    def test_timestamp_with_offset_converted_to_utc(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "job.progress",
            "occurred_at": "2026-10-31T14:00:00+02:00",
            "job_id": "cv-job-01",
            "data": {"progress": 10},
        }
        event = TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert event.occurred_at.tzinfo == timezone.utc
        assert event.occurred_at.hour == 12

    def test_progress_101_rejected(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "job.progress",
            "occurred_at": "2026-10-31T12:00:00Z",
            "job_id": "cv-job-01",
            "data": {"progress": 101},
        }
        with pytest.raises(ValidationError):
            TypeAdapter(CvEventEnvelope).validate_python(raw)

    def test_violation_confirmed_with_empty_missing_items_rejected(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "violation.confirmed",
            "occurred_at": "2026-10-31T12:00:00Z",
            "job_id": "cv-job-01",
            "data": {
                "violation_key": "vkey-1",
                "track_id": 101,
                "missing_items": [],
                "started_at": "2026-10-31T12:00:00Z",
                "started_s": 0.0,
            },
        }
        with pytest.raises(ValidationError) as exc_info:
            TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert "missing_items must not be empty" in str(exc_info.value)

    def test_violation_confirmed_with_ended_at_rejected(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "violation.confirmed",
            "occurred_at": "2026-10-31T12:00:00Z",
            "job_id": "cv-job-01",
            "data": {
                "violation_key": "vkey-1",
                "track_id": 101,
                "missing_items": ["vest"],
                "started_at": "2026-10-31T12:00:00Z",
                "started_s": 0.0,
                "ended_at": "2026-10-31T12:00:05Z",
            },
        }
        with pytest.raises(ValidationError) as exc_info:
            TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert "ended_at must be null" in str(exc_info.value)

    def test_bbox_x1_ge_x2_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBoxPx(x1=100.0, y1=10.0, x2=50.0, y2=200.0)

    def test_unknown_extra_fields_ignored(self) -> None:
        raw = {
            "contract_version": "1.0",
            "event_id": str(uuid.uuid4()),
            "type": "job.progress",
            "occurred_at": "2026-10-31T12:00:00Z",
            "job_id": "cv-job-01",
            "data": {"progress": 10},
            "future_metadata_field": "compatible",
        }
        event = TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert event.type == "job.progress"

    def test_wrong_major_version_rejected(self) -> None:
        raw = {
            "contract_version": "2.0",
            "event_id": str(uuid.uuid4()),
            "type": "job.progress",
            "occurred_at": "2026-10-31T12:00:00Z",
            "job_id": "cv-job-01",
            "data": {"progress": 10},
        }
        with pytest.raises(ValidationError) as exc_info:
            TypeAdapter(CvEventEnvelope).validate_python(raw)
        assert "Unsupported contract_version" in str(exc_info.value)


# ===========================================================================
# 2. Authentication & Security Tests
# ===========================================================================

class TestCvAuth:
    """Validate internal service-to-service authentication and log protection."""

    def test_missing_key_returns_401(self, client: TestClient) -> None:
        res = client.post(
            "/internal/api/v1/cv/events",
            json={"contract_version": "1.0", "events": []},
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid service credentials"

    def test_wrong_key_returns_401(self, client: TestClient) -> None:
        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": "incorrect-wrong-service-key-value"},
            json={"contract_version": "1.0", "events": []},
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid service credentials"

    def test_401_body_identical_for_missing_and_wrong_key(self, client: TestClient) -> None:
        res_missing = client.post("/internal/api/v1/cv/events", json={})
        res_wrong = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": "bad-key"},
            json={},
        )
        assert res_missing.json()["detail"] == res_wrong.json()["detail"]

    def test_empty_configured_key_refuses_all(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = get_settings()
        monkeypatch.setattr(settings, "CV_EVENTS_API_KEY", "")

        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json={"contract_version": "1.0", "events": []},
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid service credentials"

    def test_correct_key_returns_200(self, client: TestClient) -> None:
        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json={"contract_version": "1.0", "events": []},
        )
        assert res.status_code == 200

    def test_keys_never_appear_in_logs(self) -> None:
        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name="vision_api.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg={
                "cv_service_api_key": "top-secret-backend-key",
                "cv_events_api_key": "top-secret-events-key",
                "x-service-key": "top-secret-header-key",
            },
            args=(),
            exc_info=None,
        )
        record.cv_events_api_key = "secret_extra_key"
        filt.filter(record)

        assert record.msg["cv_service_api_key"] == "[REDACTED]"
        assert record.msg["cv_events_api_key"] == "[REDACTED]"
        assert record.msg["x-service-key"] == "[REDACTED]"
        assert record.cv_events_api_key == "[REDACTED]"


# ===========================================================================
# 3. Ingestion & Idempotency Tests
# ===========================================================================

class TestCvEventIngestion:
    """Validate intake idempotency, single and batch submission, and body constraints."""

    def test_single_event_ingestion(self, client: TestClient, db_session: Session) -> None:
        event_id = str(uuid.uuid4())
        payload = {
            "contract_version": "1.0",
            "event_id": event_id,
            "type": "job.progress",
            "occurred_at": "2026-10-31T12:00:00Z",
            "job_id": "cv-job-001",
            "data": {"progress": 20},
        }

        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json=payload,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["contract_version"] == "1.0"
        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "accepted"

        row = db_session.query(CvEvent).filter(CvEvent.event_id == event_id).first()
        assert row is not None
        assert row.outcome == "accepted"

    def test_idempotent_duplicate_event_submission(self, client: TestClient, db_session: Session) -> None:
        event_id = str(uuid.uuid4())
        payload = {
            "contract_version": "1.0",
            "event_id": event_id,
            "type": "job.progress",
            "occurred_at": "2026-10-31T12:00:00Z",
            "job_id": "cv-job-001",
            "data": {"progress": 20},
        }

        # First delivery -> accepted
        res1 = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json=payload,
        )
        assert res1.status_code == 200
        assert res1.json()["results"][0]["status"] == "accepted"

        # Second delivery with exact same event_id -> duplicate
        res2 = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json=payload,
        )
        assert res2.status_code == 200
        assert res2.json()["results"][0]["status"] == "duplicate"

        # Exactly 1 row in the database
        rows = db_session.query(CvEvent).filter(CvEvent.event_id == event_id).all()
        assert len(rows) == 1

    def test_duplicates_inside_same_batch(self, client: TestClient, db_session: Session) -> None:
        event_id = str(uuid.uuid4())
        payload = {
            "contract_version": "1.0",
            "events": [
                {
                    "contract_version": "1.0",
                    "event_id": event_id,
                    "type": "job.progress",
                    "occurred_at": "2026-10-31T12:00:00Z",
                    "job_id": "cv-job-001",
                    "data": {"progress": 10},
                },
                {
                    "contract_version": "1.0",
                    "event_id": event_id,
                    "type": "job.progress",
                    "occurred_at": "2026-10-31T12:00:00Z",
                    "job_id": "cv-job-001",
                    "data": {"progress": 10},
                },
            ],
        }

        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json=payload,
        )
        assert res.status_code == 200
        results = res.json()["results"]
        assert results[0]["status"] == "accepted"
        assert results[1]["status"] == "duplicate"

        rows = db_session.query(CvEvent).filter(CvEvent.event_id == event_id).all()
        assert len(rows) == 1

    def test_batch_with_invalid_event_accepts_valid_ones(self, client: TestClient) -> None:
        valid_id = str(uuid.uuid4())
        invalid_id = str(uuid.uuid4())
        payload = {
            "contract_version": "1.0",
            "events": [
                {
                    "contract_version": "1.0",
                    "event_id": valid_id,
                    "type": "job.progress",
                    "occurred_at": "2026-10-31T12:00:00Z",
                    "job_id": "cv-job-001",
                    "data": {"progress": 10},
                },
                {
                    "contract_version": "1.0",
                    "event_id": invalid_id,
                    "type": "violation.confirmed",
                    "occurred_at": "2026-10-31T12:00:00Z",
                    "job_id": "cv-job-001",
                    "data": {
                        "violation_key": "v1",
                        "track_id": 101,
                        "missing_items": [],  # Invalid
                        "started_at": "2026-10-31T12:00:00Z",
                        "started_s": 0.0,
                    },
                },
            ],
        }

        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json=payload,
        )
        assert res.status_code == 200
        results = res.json()["results"]
        assert results[0]["status"] == "accepted"
        assert results[1]["status"] == "rejected"
        assert results[1]["reason"] is not None

    def test_batch_exceeding_max_limit_returns_422(self, client: TestClient) -> None:
        events = [
            {
                "contract_version": "1.0",
                "event_id": str(uuid.uuid4()),
                "type": "job.progress",
                "occurred_at": "2026-10-31T12:00:00Z",
                "job_id": "cv-job-001",
                "data": {"progress": i},
            }
            for i in range(101)  # 101 > 100 limit
        ]
        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json={"contract_version": "1.0", "events": events},
        )
        assert res.status_code == 422
        assert "Batch size 101 exceeds maximum allowed" in str(res.json())

    def test_body_above_size_limit_returns_413(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        # Set body limit to 1 KB for quick testing
        settings = get_settings()
        monkeypatch.setattr(settings, "CV_EVENTS_MAX_BODY_KB", 1)

        huge_payload = {
            "contract_version": "1.0",
            "events": [
                {
                    "contract_version": "1.0",
                    "event_id": str(uuid.uuid4()),
                    "type": "job.progress",
                    "occurred_at": "2026-10-31T12:00:00Z",
                    "job_id": "cv-job-001",
                    "data": {"progress": 10},
                    "padding": "x" * 2000,
                }
            ],
        }
        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json=huge_payload,
        )
        assert res.status_code == 413
        assert "Request body exceeds maximum allowed limit" in res.json()["detail"]

    def test_unparseable_json_returns_422(self, client: TestClient) -> None:
        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY, "Content-Type": "application/json"},
            content=b"this is not valid json at all",
        )
        assert res.status_code == 422
        assert "Malformed JSON" in str(res.json())


# ===========================================================================
# 4. Job State Mutation Tests
# ===========================================================================

class TestCvJobState:
    """Validate Job entity state machine mutations driven by CV events."""

    def test_progress_transitions_pending_to_running(self, client: TestClient, db_session: Session) -> None:
        job = Job(
            id=str(uuid.uuid4()),
            type="video",
            status="pending",
            progress=0,
            input_path="uploads/test.mp4",
            cv_job_id="cv-job-prog-1",
        )
        db_session.add(job)
        db_session.commit()

        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json={
                "contract_version": "1.0",
                "event_id": str(uuid.uuid4()),
                "type": "job.progress",
                "occurred_at": "2026-10-31T12:00:00Z",
                "job_id": "cv-job-prog-1",
                "data": {"progress": 35},
            },
        )
        assert res.status_code == 200

        db_session.refresh(job)
        assert job.status == "running"
        assert job.cv_status == "running"
        assert job.progress == 35

    def test_lower_progress_value_is_ignored(self, client: TestClient, db_session: Session) -> None:
        job = Job(
            id=str(uuid.uuid4()),
            type="video",
            status="running",
            progress=50,
            input_path="uploads/test.mp4",
            cv_job_id="cv-job-prog-2",
        )
        db_session.add(job)
        db_session.commit()

        # Submit progress 40 (lower than 50)
        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json={
                "contract_version": "1.0",
                "event_id": str(uuid.uuid4()),
                "type": "job.progress",
                "occurred_at": "2026-10-31T12:00:00Z",
                "job_id": "cv-job-prog-2",
                "data": {"progress": 40},
            },
        )
        assert res.status_code == 200

        db_session.refresh(job)
        assert job.progress == 50  # Must not decrease

    def test_job_completed_sets_done(self, client: TestClient, db_session: Session) -> None:
        job = Job(
            id=str(uuid.uuid4()),
            type="video",
            status="running",
            progress=80,
            input_path="uploads/test.mp4",
            cv_job_id="cv-job-comp-1",
        )
        db_session.add(job)
        db_session.commit()

        occurred_iso = "2026-10-31T12:10:00Z"
        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json={
                "contract_version": "1.0",
                "event_id": str(uuid.uuid4()),
                "type": "job.completed",
                "occurred_at": occurred_iso,
                "job_id": "cv-job-comp-1",
                "data": {
                    "summary": {
                        "workers_tracked": 5,
                        "compliant": 4,
                        "violations": 1,
                        "uncertain": 0,
                        "unidentified_workers": 0,
                        "violation_events": 1,
                        "compliance_rate": 0.8,
                    }
                },
            },
        )
        assert res.status_code == 200

        db_session.refresh(job)
        assert job.status == "done"
        assert job.cv_status == "completed"
        assert job.progress == 100
        assert job.finished_at is not None

    def test_job_failed_sanitizes_error(self, client: TestClient, db_session: Session) -> None:
        job = Job(
            id=str(uuid.uuid4()),
            type="video",
            status="running",
            progress=20,
            input_path="uploads/test.mp4",
            cv_job_id="cv-job-fail-1",
        )
        db_session.add(job)
        db_session.commit()

        long_msg = "A" * 300
        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json={
                "contract_version": "1.0",
                "event_id": str(uuid.uuid4()),
                "type": "job.failed",
                "occurred_at": "2026-10-31T12:05:00Z",
                "job_id": "cv-job-fail-1",
                "data": {
                    "error": {
                        "code": "FATAL_OOM",
                        "message": long_msg,
                    }
                },
            },
        )
        assert res.status_code == 200

        db_session.refresh(job)
        assert job.status == "failed"
        assert job.cv_status == "failed"
        assert len(job.error) <= 200
        assert job.error.startswith("[FATAL_OOM]")

    def test_events_after_terminal_state_ignored(self, client: TestClient, db_session: Session) -> None:
        job = Job(
            id=str(uuid.uuid4()),
            type="video",
            status="done",
            progress=100,
            input_path="uploads/test.mp4",
            cv_job_id="cv-job-term-1",
        )
        db_session.add(job)
        db_session.commit()

        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json={
                "contract_version": "1.0",
                "event_id": str(uuid.uuid4()),
                "type": "job.progress",
                "occurred_at": "2026-10-31T12:00:00Z",
                "job_id": "cv-job-term-1",
                "data": {"progress": 10},
            },
        )
        assert res.status_code == 200

        db_session.refresh(job)
        assert job.status == "done"
        assert job.progress == 100

    def test_unknown_cv_job_id_accepted_and_stored(self, client: TestClient, db_session: Session) -> None:
        event_id = str(uuid.uuid4())
        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json={
                "contract_version": "1.0",
                "event_id": event_id,
                "type": "job.progress",
                "occurred_at": "2026-10-31T12:00:00Z",
                "job_id": "non-existent-cv-job-999",
                "data": {"progress": 10},
            },
        )
        assert res.status_code == 200
        assert res.json()["results"][0]["status"] == "accepted"

        row = db_session.query(CvEvent).filter(CvEvent.event_id == event_id).first()
        assert row is not None
        assert row.job_id is None
        assert row.cv_job_id == "non-existent-cv-job-999"


# ===========================================================================
# 5. Handler Registry & Error Resilience Tests
# ===========================================================================

class TestCvHandlerRegistry:
    """Validate custom handler registration, duplicate prevention, and exception isolation."""

    def test_handler_called_once_and_not_on_duplicate(self, client: TestClient) -> None:
        call_count = 0

        def my_handler(db: Session, event: Any, job: Optional[Job]) -> None:
            nonlocal call_count
            call_count += 1

        register_event_handler("job.progress", my_handler)

        event_id = str(uuid.uuid4())
        payload = {
            "contract_version": "1.0",
            "event_id": event_id,
            "type": "job.progress",
            "occurred_at": "2026-10-31T12:00:00Z",
            "job_id": "cv-job-test",
            "data": {"progress": 10},
        }

        # First call -> handler executed
        res1 = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json=payload,
        )
        assert res1.status_code == 200
        assert call_count == 1

        # Second call (duplicate) -> handler NOT executed
        res2 = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json=payload,
        )
        assert res2.status_code == 200
        assert call_count == 1

    def test_raising_handler_records_handler_failed_and_does_not_break_batch(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        def failing_handler(db: Session, event: Any, job: Optional[Job]) -> None:
            if event.event_id == "failing-event-id":
                raise RuntimeError("Simulated unhandled handler explosion")

        register_event_handler("job.progress", failing_handler)

        event_id_1 = "failing-event-id"
        event_id_2 = str(uuid.uuid4())
        payload = {
            "contract_version": "1.0",
            "events": [
                {
                    "contract_version": "1.0",
                    "event_id": event_id_1,
                    "type": "job.progress",
                    "occurred_at": "2026-10-31T12:00:00Z",
                    "job_id": "cv-job-hfail",
                    "data": {"progress": 10},
                },
                {
                    "contract_version": "1.0",
                    "event_id": event_id_2,
                    "type": "job.progress",
                    "occurred_at": "2026-10-31T12:00:00Z",
                    "job_id": "cv-job-hfail",
                    "data": {"progress": 20},
                },
            ],
        }

        res = client.post(
            "/internal/api/v1/cv/events",
            headers={"X-Service-Key": VALID_KEY},
            json=payload,
        )
        assert res.status_code == 200
        results = res.json()["results"]
        # Both must still be reported accepted to the CV service
        assert results[0]["status"] == "accepted"
        assert results[1]["status"] == "accepted"

        row1 = db_session.query(CvEvent).filter(CvEvent.event_id == event_id_1).first()
        assert row1 is not None
        assert row1.outcome == "handler_failed"
        assert "Simulated unhandled handler explosion" in (row1.error or "")

        row2 = db_session.query(CvEvent).filter(CvEvent.event_id == event_id_2).first()
        assert row2 is not None
        assert row2.outcome == "accepted"


# ===========================================================================
# 6. Startup Security & Key Safety Tests
# ===========================================================================

class TestCvStartupSafety:
    """Validate startup verification for CV_SERVICE_API_KEY and CV_EVENTS_API_KEY."""

    def test_production_refuses_startup_if_cv_keys_short_or_empty(self) -> None:
        # Short CV_SERVICE_API_KEY
        s1 = Settings(
            DEBUG=False,
            SECRET_KEY="production-secret-key-32-chars-long-123456",
            ALLOWED_ORIGINS=["http://localhost:8000"],
            CV_SERVICE_API_KEY="short-key",
            CV_EVENTS_API_KEY="sufficiently-long-events-api-key-32-chars-123",
        )
        with pytest.raises(RuntimeError) as exc1:
            validate_startup_settings(s1)
        assert "CV_SERVICE_API_KEY must be set and at least 32 characters" in str(exc1.value)

        # Short CV_EVENTS_API_KEY
        s2 = Settings(
            DEBUG=False,
            SECRET_KEY="production-secret-key-32-chars-long-123456",
            ALLOWED_ORIGINS=["http://localhost:8000"],
            CV_SERVICE_API_KEY="sufficiently-long-service-api-key-32-chars-12",
            CV_EVENTS_API_KEY="short",
        )
        with pytest.raises(RuntimeError) as exc2:
            validate_startup_settings(s2)
        assert "CV_EVENTS_API_KEY must be set and at least 32 characters" in str(exc2.value)

    def test_production_refuses_startup_if_cv_keys_are_equal(self) -> None:
        same_key = "identical-secret-key-that-is-32-characters-long"
        s = Settings(
            DEBUG=False,
            SECRET_KEY="production-secret-key-32-chars-long-123456",
            ALLOWED_ORIGINS=["http://localhost:8000"],
            CV_SERVICE_API_KEY=same_key,
            CV_EVENTS_API_KEY=same_key,
        )
        with pytest.raises(RuntimeError) as exc:
            validate_startup_settings(s)
        assert "CV_SERVICE_API_KEY and CV_EVENTS_API_KEY must differ" in str(exc.value)

    def test_debug_mode_only_warns_on_empty_keys(self, caplog: pytest.LogCaptureFixture) -> None:
        s = Settings(
            DEBUG=True,
            SECRET_KEY="dev-secret-key-placeholder-32-chars-long",
            CV_SERVICE_API_KEY="",
            CV_EVENTS_API_KEY="",
        )
        with caplog.at_level(logging.WARNING):
            validate_startup_settings(s)
        assert any("CV_SERVICE_API_KEY is empty" in record.message for record in caplog.records)
        assert any("CV_EVENTS_API_KEY is empty" in record.message for record in caplog.records)


# ===========================================================================
# 7. Database Migration Tests
# ===========================================================================

class TestCvMigration:
    """Verify that Alembic migrations create all new columns and tables on fresh databases."""

    def test_upgrade_creates_cv_columns_and_table(self, tmp_path: Any) -> None:
        db_file = tmp_path / "fresh_migration_test.db"
        db_url = f"sqlite:///{db_file.as_posix()}"

        engine = create_engine(db_url)
        with engine.begin() as connection:
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.attributes["connection"] = connection
            command.upgrade(alembic_cfg, "head")

        inspector = inspect(engine)

        # Check jobs table columns
        jobs_cols = {col["name"] for col in inspector.get_columns("jobs")}
        assert "cv_job_id" in jobs_cols
        assert "source_type" in jobs_cols
        assert "camera_name" in jobs_cols
        assert "required_equipment" in jobs_cols
        assert "cv_status" in jobs_cols
        assert "finished_at" in jobs_cols

        # Check cv_events table
        tables = set(inspector.get_table_names())
        assert "cv_events" in tables

        cv_event_cols = {col["name"] for col in inspector.get_columns("cv_events")}
        expected_cv_cols = {
            "event_id",
            "job_id",
            "cv_job_id",
            "type",
            "occurred_at",
            "received_at",
            "sequence",
            "payload",
            "outcome",
            "error",
        }
        assert expected_cv_cols.issubset(cv_event_cols)
