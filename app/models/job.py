"""Job ORM model for asynchronous and batch processing tasks."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Job(Base):
    """Job entity representing processing tasks for images, videos, and streams."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("type IN ('image', 'video', 'stream')", name="check_job_type"),
        CheckConstraint("status IN ('pending', 'running', 'done', 'failed')", name="check_job_status"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="check_job_progress"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        index=True,
        nullable=False,
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # CV microservice integration fields (nullable)
    cv_job_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=True,
    )
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    camera_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    required_equipment: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    cv_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Job(id='{self.id}', type='{self.type}', status='{self.status}', progress={self.progress})>"
