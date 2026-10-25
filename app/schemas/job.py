"""Pydantic schemas for background jobs and task status tracking."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class JobSubmitOut(BaseModel):
    """Response returned upon submitting an asynchronous processing job (HTTP 202)."""

    job_id: str = Field(..., description="Unique job identifier UUID")
    status: str = Field(..., description="Initial job status ('pending')")
    progress: int = Field(0, description="Initial progress percentage (0 to 100)")
    created_at: datetime = Field(..., description="Timestamp of submission")

    model_config = ConfigDict(from_attributes=True)


class JobOut(BaseModel):
    """Detailed job status and result schema."""

    id: str = Field(..., description="Unique job identifier UUID")
    user_id: Optional[int] = Field(None, description="Owning user ID")
    type: str = Field(..., description="Job type ('image', 'video', 'stream')")
    status: str = Field(..., description="Current status ('pending', 'running', 'done', 'failed')")
    progress: int = Field(..., description="Processing progress percentage (0 to 100)")
    input_path: Optional[str] = Field(None, description="Path to stored input file")
    result: Optional[Dict[str, Any]] = Field(
        None,
        description="Inference summary, timeline, and peak frame results (only when status is 'done')",
    )
    error: Optional[str] = Field(None, description="Sanitized error description on failure")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last status update timestamp")

    model_config = ConfigDict(from_attributes=True)
