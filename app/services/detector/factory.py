"""Detector factory function resolving detector backend instances."""

from typing import Optional

from app.core.config import Settings, get_settings
from app.services.detector.base import BaseDetector
from app.services.detector.dummy import DummyDetector
from app.services.detector.yolo_detector import YoloDetector

VALID_BACKENDS = ("dummy", "yolo")


def get_detector(settings: Optional[Settings] = None) -> BaseDetector:
    """Instantiate and return the configured BaseDetector implementation.

    Args:
        settings: Application Settings instance. Defaults to get_settings().

    Returns:
        BaseDetector: Instantiated detector backend (DummyDetector or YoloDetector).

    Raises:
        ValueError: If DETECTOR_BACKEND is unrecognized.
    """
    if settings is None:
        settings = get_settings()

    backend = (settings.DETECTOR_BACKEND or "").strip().lower()

    if backend == "dummy":
        return DummyDetector(confidence_threshold=settings.CONFIDENCE_THRESHOLD)
    elif backend == "yolo":
        return YoloDetector(
            model_path=settings.MODEL_PATH,
            confidence_threshold=settings.CONFIDENCE_THRESHOLD,
        )
    else:
        raise ValueError(
            f"Invalid DETECTOR_BACKEND '{settings.DETECTOR_BACKEND}'. "
            f"Supported options are: {', '.join(VALID_BACKENDS)}."
        )
