"""Dummy detector returning deterministic mock object detections without ML libraries."""

import hashlib
import random
import time
from typing import List, Optional
from PIL import Image

from app.core.config import get_settings
from app.schemas.detection import BoundingBox, DetectedObject, DetectionResult
from app.services.detector.base import BaseDetector

CANDIDATE_LABELS = [
    "person",
    "car",
    "bicycle",
    "dog",
    "cat",
    "backpack",
    "traffic light",
    "chair",
    "laptop",
    "cell phone",
]


class DummyDetector(BaseDetector):
    """Deterministic mock object detector for testing and development.

    Requires zero GPU, PyTorch, Ultralytics, OpenCV, or NumPy dependencies.
    Produces deterministic bounding boxes by seeding a pseudo-random number generator
    from a SHA-256 hash of the image dimensions and raw pixel bytes.
    """

    def __init__(self, confidence_threshold: Optional[float] = None) -> None:
        self.name: str = "dummy"
        self._is_loaded: bool = False
        if confidence_threshold is None:
            self.confidence_threshold = get_settings().CONFIDENCE_THRESHOLD
        else:
            self.confidence_threshold = confidence_threshold

    @property
    def is_placeholder(self) -> bool:
        """Indicate that this is a simulated placeholder detector."""
        return True

    @property
    def is_loaded(self) -> bool:
        """Return True only after load() has been called."""
        return self._is_loaded

    def load(self) -> None:
        """Simulate loading model weights into memory."""
        self._is_loaded = True

    def detect(self, image: Image.Image) -> DetectionResult:
        """Generate deterministic mock bounding boxes and labels for the given image.

        Args:
            image: Decoded PIL Image in RGB format.

        Returns:
            DetectionResult: Simulated detection output filtered by confidence threshold.
        """
        if not self._is_loaded:
            raise RuntimeError("Detector is not loaded. Call load() before running detect().")

        start_time = time.perf_counter()

        width, height = image.size
        w_float, h_float = float(width), float(height)

        # Build a deterministic seed from the image dimensions and sample pixel bytes
        sample_w = min(width, 32)
        sample_h = min(height, 32)
        try:
            # Crop a small corner to avoid reading massive pixel buffers
            sample_bytes = image.crop((0, 0, sample_w, sample_h)).tobytes()
        except Exception:
            sample_bytes = b""

        seed_data = f"{width}x{height}:{len(sample_bytes)}:".encode("utf-8") + sample_bytes
        hash_digest = hashlib.sha256(seed_data).hexdigest()
        seed_int = int(hash_digest[:16], 16)

        rng = random.Random(seed_int)

        # 0 to 6 detected candidate objects
        num_candidates = rng.randint(0, 6)
        detected_objects: List[DetectedObject] = []

        for _ in range(num_candidates):
            # Select label
            label = rng.choice(CANDIDATE_LABELS)

            # Confidence between 0.30 and 0.99
            confidence = round(rng.uniform(0.30, 0.99), 4)

            # Generate bounding boxes strictly inside image bounds with x1 < x2 and y1 < y2
            # Generate normalized fraction coordinates with minimum span
            nx1 = rng.uniform(0.02, 0.70)
            nx2 = rng.uniform(nx1 + 0.05, 0.98)
            ny1 = rng.uniform(0.02, 0.70)
            ny2 = rng.uniform(ny1 + 0.05, 0.98)

            px1 = round(nx1 * w_float, 2)
            px2 = round(nx2 * w_float, 2)
            py1 = round(ny1 * h_float, 2)
            py2 = round(ny2 * h_float, 2)

            # Ensure strict invariants: 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height
            px1 = max(0.0, min(px1, w_float - 1.0))
            px2 = max(px1 + 1.0, min(px2, w_float))
            py1 = max(0.0, min(py1, h_float - 1.0))
            py2 = max(py1 + 1.0, min(py2, h_float))

            detected_objects.append(
                DetectedObject(
                    label=label,
                    confidence=confidence,
                    bbox=BoundingBox(x1=px1, y1=py1, x2=px2, y2=py2),
                )
            )

        # Filter candidates by CONFIDENCE_THRESHOLD
        filtered_objects = [
            obj for obj in detected_objects if obj.confidence >= self.confidence_threshold
        ]

        inference_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return DetectionResult(
            objects=filtered_objects,
            total_count=len(filtered_objects),
            image_width=width,
            image_height=height,
            inference_ms=inference_ms,
            detector_name=self.name,
            extra={"note": "placeholder detections, not real"},
        )

    def close(self) -> None:
        """Reset loaded state on shutdown."""
        self._is_loaded = False
