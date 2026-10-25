"""Pydantic schemas for object detection results and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BoundingBox(BaseModel):
    """Bounding box pixel coordinates (top-left x1, y1 and bottom-right x2, y2)."""

    x1: float = Field(..., description="Top-left X pixel coordinate")
    y1: float = Field(..., description="Top-left Y pixel coordinate")
    x2: float = Field(..., description="Bottom-right X pixel coordinate")
    y2: float = Field(..., description="Bottom-right Y pixel coordinate")


class DetectedObject(BaseModel):
    """An individual detected object entity."""

    label: str = Field(..., description="Class label name (e.g., person, car)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    bbox: BoundingBox = Field(..., description="Bounding box pixel coordinates")


class DetectionResult(BaseModel):
    """Complete inference results returned by any detector implementation."""

    objects: List[DetectedObject] = Field(default_factory=list, description="List of detected objects")
    total_count: int = Field(..., ge=0, description="Total number of detected objects")
    image_width: int = Field(..., gt=0, description="Image width in pixels")
    image_height: int = Field(..., gt=0, description="Image height in pixels")
    inference_ms: float = Field(..., ge=0.0, description="Inference latency in milliseconds")
    detector_name: str = Field(..., description="Name of the detector model used")
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible metadata dictionary for detector-specific additions",
    )


class DetectionOut(BaseModel):
    """API response schema for stored detection records."""

    id: int
    source_type: str
    detector_name: str
    total_count: int
    file_path: Optional[str] = None
    results: DetectionResult
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
