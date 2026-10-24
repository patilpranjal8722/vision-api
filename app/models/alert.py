"""Alert ORM model for notifications triggered by computer vision events."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Alert(Base):
    """Alert entity recording security, threshold, or diagnostic notifications."""

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("level IN ('info', 'warning', 'critical')", name="check_alert_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    detection_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("detections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, level='{self.level}', is_read={self.is_read})>"
