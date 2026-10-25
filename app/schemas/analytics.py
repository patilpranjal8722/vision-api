"""Pydantic schemas for analytics endpoints."""

from typing import Dict
from pydantic import BaseModel


class AnalyticsSummaryOut(BaseModel):
    """Aggregated summary of detection and alert statistics."""

    total_detections: int
    total_objects: int
    avg_count: float
    max_count: int
    counts_by_source: Dict[str, int]
    alerts_by_level: Dict[str, int]
    top_labels: Dict[str, int]
    truncated: bool


class TimeseriesBucket(BaseModel):
    """Single time-bucket within an analytics timeseries."""

    bucket_start: str
    detections: int
    avg_count: float
    max_count: int
