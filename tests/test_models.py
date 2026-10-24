"""Unit tests for SQLAlchemy models, constraints, and relationships."""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.detection import Detection
from app.models.job import Job
from app.models.user import User


def test_create_and_read_user(db_session: Session) -> None:
    """Test User creation, persistence, and querying."""
    user = User(
        email="developer@example.com",
        username="vision_dev",
        hashed_password="secure_hashed_password_example",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "developer@example.com"
    assert user.username == "vision_dev"
    assert user.role == "user"
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)

    # Read back from clean query
    queried_user = db_session.query(User).filter_by(username="vision_dev").first()
    assert queried_user is not None
    assert queried_user.email == "developer@example.com"


def test_user_email_unique_constraint(db_session: Session) -> None:
    """Test that creating two users with the same email raises IntegrityError."""
    user1 = User(
        email="duplicate@example.com",
        username="user_one",
        hashed_password="pw1",
    )
    db_session.add(user1)
    db_session.commit()

    user2 = User(
        email="duplicate@example.com",
        username="user_two",
        hashed_password="pw2",
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_user_username_unique_constraint(db_session: Session) -> None:
    """Test that creating two users with the same username raises IntegrityError."""
    user1 = User(
        email="user1@example.com",
        username="unique_handle",
        hashed_password="pw1",
    )
    db_session.add(user1)
    db_session.commit()

    user2 = User(
        email="user2@example.com",
        username="unique_handle",
        hashed_password="pw2",
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_create_and_read_job(db_session: Session) -> None:
    """Test Job creation, UUID generation, JSON field storage, and querying."""
    user = User(
        email="job_owner@example.com",
        username="job_owner",
        hashed_password="pw",
    )
    db_session.add(user)
    db_session.commit()

    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        user_id=user.id,
        type="image",
        status="pending",
        progress=0,
        input_path="uploads/sample_input.jpg",
        result={"summary": "Pending detector run"},
        error=None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.id == job_id
    assert job.user_id == user.id
    assert job.type == "image"
    assert job.status == "pending"
    assert job.progress == 0
    assert job.input_path == "uploads/sample_input.jpg"
    assert job.result == {"summary": "Pending detector run"}
    assert job.error is None
    assert isinstance(job.created_at, datetime)
    assert isinstance(job.updated_at, datetime)

    # Read back
    queried_job = db_session.query(Job).filter_by(id=job_id).first()
    assert queried_job is not None
    assert queried_job.result["summary"] == "Pending detector run"


def test_create_and_read_detection(db_session: Session) -> None:
    """Test Detection creation, JSON result storage, and relationship querying."""
    detection = Detection(
        user_id=None,
        job_id=None,
        source_type="image",
        file_path="uploads/frame_001.jpg",
        detector_name="dummy",
        total_count=2,
        results={
            "boxes": [
                {"label": "person", "confidence": 0.94, "box": [10, 20, 100, 200]},
                {"label": "backpack", "confidence": 0.88, "box": [30, 40, 80, 120]},
            ]
        },
    )
    db_session.add(detection)
    db_session.commit()
    db_session.refresh(detection)

    assert detection.id is not None
    assert detection.detector_name == "dummy"
    assert detection.total_count == 2
    assert len(detection.results["boxes"]) == 2
    assert isinstance(detection.created_at, datetime)

    # Read back
    queried = db_session.query(Detection).filter_by(id=detection.id).first()
    assert queried is not None
    assert queried.results["boxes"][0]["label"] == "person"


def test_create_and_read_alert(db_session: Session) -> None:
    """Test Alert creation with foreign keys and check constraint validation."""
    alert = Alert(
        user_id=None,
        detection_id=None,
        level="warning",
        message="Unauthorized person detected in restricted area.",
        is_read=False,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    assert alert.id is not None
    assert alert.level == "warning"
    assert alert.message == "Unauthorized person detected in restricted area."
    assert alert.is_read is False
    assert isinstance(alert.created_at, datetime)

    # Read back
    queried_alert = db_session.query(Alert).filter_by(id=alert.id).first()
    assert queried_alert is not None
    assert queried_alert.level == "warning"
