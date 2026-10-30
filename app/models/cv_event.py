"""CvEvent ORM model for storing raw incoming CV microservice event envelopes."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CvEvent(Base):
    """Stores incoming event envelopes from the CV microservice for audit and idempotency."""

    __tablename__ = "cv_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cv_job_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    sequence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), default="accepted", nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<CvEvent(event_id='{self.event_id}', type='{self.type}', outcome='{self.outcome}')>"
