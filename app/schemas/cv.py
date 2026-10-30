"""Pydantic v2 schemas for the CV microservice integration contract (v1.0).

Defines event envelopes, payloads, shared models, and intake response shapes.
All timestamps are timezone-aware and normalized to UTC.
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Allowed flags for worker observations
AllowedFlag = Literal[
    "helmet_in_hand",
    "helmet_not_on_head",
    "hi_vis_not_vest",
    "partly_occluded",
    "low_light",
    "small_or_distant",
]


def ensure_utc_aware(v: Any) -> datetime:
    """Validate that datetime is timezone-aware and convert to UTC."""
    if not isinstance(v, datetime):
        raise ValueError("Invalid datetime value.")
    if v.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return v.astimezone(timezone.utc)


def validate_why_list(v: List[str]) -> List[str]:
    """Ensure why items are at most 10 items and max 200 characters each."""
    if len(v) > 10:
        raise ValueError("why list cannot contain more than 10 items.")
    for i, item in enumerate(v):
        if len(item) > 200:
            raise ValueError(f"why item at index {i} exceeds maximum length of 200 characters.")
    return v


def validate_major_version(v: str) -> str:
    """Validate that contract_version has major version 1."""
    parts = v.strip().split(".")
    if not parts or parts[0] != "1":
        raise ValueError(f"Unsupported contract_version '{v}'. Expected major version 1 (e.g. '1.0').")
    return v


# ---------------------------------------------------------------------------
# Shared Sub-Models
# ---------------------------------------------------------------------------

class ItemStatus(BaseModel):
    """Observation status of a single piece of protective equipment."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["present", "missing", "uncertain"]
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class Identity(BaseModel):
    """Worker identity evidence detected by CV service."""

    model_config = ConfigDict(extra="ignore")

    method: Optional[Literal["ocr", "marker"]] = None
    code: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    verified: bool = False


class Items(BaseModel):
    """Protective equipment items evaluated for a worker."""

    model_config = ConfigDict(extra="ignore")

    helmet: ItemStatus
    vest: ItemStatus


class BoundingBoxPx(BaseModel):
    """Absolute pixel bounding box in the original frame."""

    model_config = ConfigDict(extra="ignore")

    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def validate_coordinates(self) -> "BoundingBoxPx":
        if self.x1 >= self.x2:
            raise ValueError(f"Bounding box x1 ({self.x1}) must be strictly less than x2 ({self.x2}).")
        if self.y1 >= self.y2:
            raise ValueError(f"Bounding box y1 ({self.y1}) must be strictly less than y2 ({self.y2}).")
        return self


class WorkerState(BaseModel):
    """State transition payload sent when worker status or identity changes."""

    model_config = ConfigDict(extra="ignore")

    track_id: int = Field(ge=1)
    verdict: Literal["compliant", "violation", "uncertain"]
    items: Items
    identity: Optional[Identity] = None
    flags: List[AllowedFlag] = Field(default_factory=list)
    why: List[str] = Field(default_factory=list)
    bbox: BoundingBoxPx
    frame_index: Optional[int] = Field(None, ge=0)
    timestamp_s: Optional[float] = Field(None, ge=0.0)

    @field_validator("why")
    @classmethod
    def check_why(cls, v: List[str]) -> List[str]:
        return validate_why_list(v)


class ViolationData(BaseModel):
    """Confirmed violation episode data."""

    model_config = ConfigDict(extra="ignore")

    violation_key: str = Field(min_length=1)
    track_id: int = Field(ge=1)
    missing_items: List[Literal["helmet", "vest"]]
    started_at: datetime
    started_s: float = Field(ge=0.0)
    ended_at: Optional[datetime] = None
    duration_s: Optional[float] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    identity: Optional[Identity] = None
    snapshot_artifact_id: Optional[str] = None
    why: List[str] = Field(default_factory=list)

    @field_validator("started_at", mode="after")
    @classmethod
    def check_started_at(cls, v: datetime) -> datetime:
        return ensure_utc_aware(v)

    @field_validator("ended_at", mode="after")
    @classmethod
    def check_ended_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None:
            raise ValueError("ended_at must be null for violation.confirmed.")
        return v

    @field_validator("missing_items")
    @classmethod
    def check_missing_items(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("missing_items must not be empty.")
        valid_items = {"helmet", "vest"}
        seen = set()
        for item in v:
            if item not in valid_items:
                raise ValueError(f"Invalid equipment item: '{item}'. Must be 'helmet' or 'vest'.")
            if item in seen:
                raise ValueError(f"Duplicate equipment item: '{item}'. Items must be unique.")
            seen.add(item)
        return v

    @field_validator("why")
    @classmethod
    def check_why(cls, v: List[str]) -> List[str]:
        return validate_why_list(v)


class ViolationEndedData(BaseModel):
    """Payload sent when an ongoing violation episode concludes."""

    model_config = ConfigDict(extra="ignore")

    violation_key: str = Field(min_length=1)
    ended_at: datetime
    duration_s: float = Field(ge=0.0)

    @field_validator("ended_at", mode="after")
    @classmethod
    def check_ended_at(cls, v: datetime) -> datetime:
        return ensure_utc_aware(v)


class JobProgressData(BaseModel):
    """Progress update for an asynchronous processing task."""

    model_config = ConfigDict(extra="ignore")

    progress: int = Field(ge=0, le=100)
    frames_processed: Optional[int] = Field(None, ge=0)


class JobSummary(BaseModel):
    """Aggregate summary statistics compiled by the CV microservice."""

    model_config = ConfigDict(extra="ignore")

    workers_tracked: int = Field(ge=0)
    compliant: int = Field(ge=0)
    violations: int = Field(ge=0)
    uncertain: int = Field(ge=0)
    unidentified_workers: int = Field(default=0, ge=0)
    violation_events: int = Field(default=0, ge=0)
    compliance_rate: Optional[float] = Field(None, ge=0.0, le=1.0)


class JobCompletedData(BaseModel):
    """Payload sent upon successful job completion."""

    model_config = ConfigDict(extra="ignore")

    summary: JobSummary


class JobError(BaseModel):
    """Structured error descriptor."""

    model_config = ConfigDict(extra="ignore")

    code: str = Field(min_length=1, max_length=50)
    message: str = Field(min_length=1)


class JobFailedData(BaseModel):
    """Payload sent upon job failure."""

    model_config = ConfigDict(extra="ignore")

    error: JobError


class CameraStatusData(BaseModel):
    """Camera connection telemetry for RTSP streams."""

    model_config = ConfigDict(extra="ignore")

    state: Literal["connected", "reconnecting", "disconnected"]
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Event Envelopes
# ---------------------------------------------------------------------------

class BaseCvEvent(BaseModel):
    """Base envelope fields shared by all incoming CV events."""

    model_config = ConfigDict(extra="ignore")

    contract_version: str = Field(default="1.0")
    event_id: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    job_id: str = Field(min_length=1, max_length=100)
    external_job_id: Optional[str] = None
    sequence: Optional[int] = Field(None, ge=0)

    @field_validator("contract_version")
    @classmethod
    def check_contract_version(cls, v: str) -> str:
        return validate_major_version(v)

    @field_validator("occurred_at", mode="after")
    @classmethod
    def check_occurred_at(cls, v: datetime) -> datetime:
        return ensure_utc_aware(v)


class JobProgressEvent(BaseCvEvent):
    type: Literal["job.progress"] = "job.progress"
    data: JobProgressData


class JobCompletedEvent(BaseCvEvent):
    type: Literal["job.completed"] = "job.completed"
    data: JobCompletedData


class JobFailedEvent(BaseCvEvent):
    type: Literal["job.failed"] = "job.failed"
    data: JobFailedData


class WorkerStatusEvent(BaseCvEvent):
    type: Literal["worker.status"] = "worker.status"
    data: WorkerState


class ViolationConfirmedEvent(BaseCvEvent):
    type: Literal["violation.confirmed"] = "violation.confirmed"
    data: ViolationData


class ViolationEndedEvent(BaseCvEvent):
    type: Literal["violation.ended"] = "violation.ended"
    data: ViolationEndedData


class CameraStatusEvent(BaseCvEvent):
    type: Literal["camera.status"] = "camera.status"
    data: CameraStatusData


# Discriminated union of all supported CV events
CvEventEnvelope = Annotated[
    Union[
        JobProgressEvent,
        JobCompletedEvent,
        JobFailedEvent,
        WorkerStatusEvent,
        ViolationConfirmedEvent,
        ViolationEndedEvent,
        CameraStatusEvent,
    ],
    Field(discriminator="type"),
]


class CvEventBatch(BaseModel):
    """Batch container for up to 100 CV event envelopes."""

    model_config = ConfigDict(extra="ignore")

    contract_version: Optional[str] = None
    events: List[Dict[str, Any]]

    @field_validator("contract_version")
    @classmethod
    def check_contract_version(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_major_version(v)
        return v


# ---------------------------------------------------------------------------
# Response Schemas for Event Intake
# ---------------------------------------------------------------------------

class CvEventResult(BaseModel):
    """Per-event processing outcome returned to the CV microservice."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    status: Literal["accepted", "duplicate", "rejected"]
    reason: Optional[str] = None


class CvEventsResponse(BaseModel):
    """Response returned by POST /internal/api/v1/cv/events."""

    model_config = ConfigDict(extra="ignore")

    contract_version: str = "1.0"
    results: List[CvEventResult]
