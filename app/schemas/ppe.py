"""Pydantic schemas for PPE (Personal Protective Equipment) compliance detection.

Defines the contract between detectors (YOLO / PPE dummy) and the rules engine.
"""

import warnings
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.detection import BoundingBox

warnings.filterwarnings(
    "ignore",
    message=r'.*Field name "schema" in .* shadows an attribute in parent "BaseModel".*',
    category=UserWarning,
)

ItemStatus = Literal["present", "missing", "uncertain"]
Verdict = Literal["compliant", "violation", "uncertain"]
Equipment = Literal["helmet", "vest"]

ALLOWED_FLAGS = {
    "helmet_in_hand",
    "helmet_not_on_head",
    "hi_vis_not_vest",
    "partly_occluded",
    "low_light",
    "small_or_distant",
}

ORDERED_EQUIPMENT = ("helmet", "vest")


class PpeItem(BaseModel):
    """Detection status and bounding box for an individual equipment item on a worker."""

    status: ItemStatus = Field(..., description="Status of the equipment item")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0) for present or missing; null for uncertain",
    )
    bbox: Optional[BoundingBox] = Field(
        default=None,
        description="Bounding box of the item assigned to this worker (only when present)",
    )


class PpeWorkerRaw(BaseModel):
    """Raw detector perception data for a detected worker before rules are applied."""

    id: int = Field(..., ge=1, description="Sequential 1-indexed worker ID ordered left to right")
    bbox: BoundingBox = Field(..., description="Bounding box of the detected person")
    person_confidence: float = Field(..., ge=0.0, le=1.0, description="Person detection confidence")
    helmet: PpeItem = Field(..., description="Helmet status on this worker")
    vest: PpeItem = Field(..., description="Vest status on this worker")
    badge_id: Optional[int] = Field(
        default=None,
        ge=0,
        le=49,
        description="Optional detected visual badge identifier index (0 to 49)",
    )
    flags: List[str] = Field(
        default_factory=list,
        description="Visual observation tags from the allowed flags set",
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Short plain-text observations (each up to 200 characters)",
    )


class PpeWorker(PpeWorkerRaw):
    """Enriched worker model after compliance rules evaluation."""

    verdict: Verdict = Field(..., description="Overall compliance verdict for this worker")
    missing: List[str] = Field(
        default_factory=list,
        description="List of required equipment items that are missing",
    )
    uncertain_items: List[str] = Field(
        default_factory=list,
        description="List of required equipment items that are uncertain",
    )
    why: List[str] = Field(
        default_factory=list,
        description="Explanatory sentences justifying the compliance verdict",
    )
    worker_id: Optional[int] = Field(
        default=None,
        description="Database identifier of the worker if identified in registry",
    )
    worker_name: Optional[str] = Field(
        default=None,
        description="Human-readable name of the worker if identified in registry",
    )
    identified: bool = Field(
        default=False,
        description="Whether the worker was identified in the workforce registry",
    )


class UnassignedItem(BaseModel):
    """An equipment detection not associated with any worker."""

    label: Equipment = Field(..., description="Item category (helmet or vest)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    bbox: BoundingBox = Field(..., description="Bounding box of the unassigned item")
    reason: str = Field(..., description="Explanation of why item was not assigned to a worker")


class PpePipelineInfo(BaseModel):
    """Metadata regarding preprocessing and inference pipeline stages."""

    low_light_enhanced: bool = Field(
        default=False,
        description="Whether low-light enhancement was applied to the frame",
    )
    zoom_pass_workers: List[int] = Field(
        default_factory=list,
        description="List of worker IDs that received a high-resolution zoom pass",
    )


class PpeSummary(BaseModel):
    """Aggregated compliance summary metrics for the frame/image."""

    workers: int = Field(..., ge=0, description="Total number of workers detected")
    compliant: int = Field(..., ge=0, description="Count of compliant workers")
    violations: int = Field(..., ge=0, description="Count of violating workers")
    uncertain: int = Field(..., ge=0, description="Count of workers with uncertain status")
    missing_helmet: int = Field(
        ...,
        ge=0,
        description="Count of workers where helmet is required and missing",
    )
    missing_vest: int = Field(
        ...,
        ge=0,
        description="Count of workers where vest is required and missing",
    )
    compliance_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Ratio of compliant workers over total workers (null if no workers)",
    )
    violating_worker_ids: List[int] = Field(
        default_factory=list,
        description="IDs of workers with violation verdicts",
    )
    required_equipment: List[str] = Field(
        default_factory=list,
        description="List of required equipment applied during rule evaluation",
    )


class PpeExtraRaw(BaseModel):
    """Raw detector output stored in DetectionResult.extra before rules engine processing."""

    schema: Literal["ppe.v1"] = "ppe.v1"
    workers: List[PpeWorkerRaw] = Field(default_factory=list)
    unassigned_items: List[UnassignedItem] = Field(default_factory=list)
    pipeline: PpePipelineInfo = Field(default_factory=PpePipelineInfo)


class PpeExtra(BaseModel):
    """Final PPE compliance metadata payload stored in DetectionResult.extra."""

    schema: Literal["ppe.v1"] = "ppe.v1"
    workers: List[PpeWorker] = Field(default_factory=list)
    unassigned_items: List[UnassignedItem] = Field(default_factory=list)
    pipeline: PpePipelineInfo = Field(default_factory=PpePipelineInfo)
    summary: PpeSummary
    required_equipment: List[str] = Field(default_factory=list)
    camera_name: Optional[str] = Field(
        default=None,
        description="Optional camera identifier or location name",
    )


class DetectorConfigOut(BaseModel):
    """Metadata about the active detector backend."""

    name: str
    is_placeholder: bool
    loaded: bool


class PpeConfigOut(BaseModel):
    """PPE domain configuration."""

    schema: str = "ppe.v1"
    supported_equipment: List[str] = list(ORDERED_EQUIPMENT)
    default_required_equipment: List[str]


class UploadConfigOut(BaseModel):
    """File upload size and format constraints."""

    max_image_mb: int
    allowed_image_types: List[str]
    max_image_dimension: int
    max_video_mb: int
    allowed_video_types: List[str]


class DetectConfigOut(BaseModel):
    """Configuration endpoint response schema."""

    detector: DetectorConfigOut
    ppe: PpeConfigOut
    upload: UploadConfigOut
    confidence_threshold: float
