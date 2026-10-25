"""Pydantic schemas for alert serialization and responses."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AlertOut(BaseModel):
    """Schema for alert responses."""

    id: int
    user_id: Optional[int] = None
    detection_id: Optional[int] = None
    level: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    """Schema for unread alert count response."""

    unread_count: int


class ReadAllOut(BaseModel):
    """Schema for read-all alerts response."""

    message: str
    updated_count: int
