"""Stub implementation of YoloDetector for the CV/ML partner.

IMPORTANT FOR DEVELOPERS & PARTNERS:
-----------------------------------
Do NOT import torch, ultralytics, cv2, or numpy at module top-level!
All ML dependencies must be lazily imported inside methods (such as load())
so that the lightweight FastAPI application and test suite can boot and run
without requiring GPU drivers or heavy ML libraries installed.
"""

from typing import Optional
from PIL import Image

from app.core.config import get_settings
from app.schemas.detection import DetectionResult
from app.services.detector.base import BaseDetector


class YoloDetector(BaseDetector):
    """Ultralytics YOLO detector stub awaiting partner implementation.

    Attributes:
        name: Identifier for this detector ("yolo").
        model_path: Path to the YOLO weights file (e.g. models_store/yolov8n.pt).
        confidence_threshold: Minimum confidence score to retain detections.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
    ) -> None:
        self.name: str = "yolo"
        self._is_loaded: bool = False
        settings = get_settings()
        self.model_path = model_path or settings.MODEL_PATH
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.CONFIDENCE_THRESHOLD
        )
        self.model = None

    @property
    def is_placeholder(self) -> bool:
        """Indicate whether this is a placeholder."""
        return False

    @property
    def is_loaded(self) -> bool:
        """Return True only after model weights have been loaded into memory."""
        return self._is_loaded

    def load(self) -> None:
        """Load YOLO model weights into memory.

        TODO for Partner:
        -----------------
        1. Install requirements-cv.txt:
           pip install -r requirements-cv.txt
        2. Perform lazy import of Ultralytics INSIDE this method:
           from ultralytics import YOLO
        3. Load weights from self.model_path (e.g., 'models_store/yolov8n.pt'):
           self.model = YOLO(self.model_path)
        4. Set self._is_loaded = True
        """
        raise NotImplementedError(
            "YOLO detector is not implemented yet. "
            "Install requirements-cv.txt, place model weights in models_store/, "
            "and implement load() and detect() in app/services/detector/yolo_detector.py."
        )

    def detect(self, image: Image.Image) -> DetectionResult:
        """Run YOLO inference on a decoded PIL image.

        Args:
            image: PIL.Image.Image in RGB mode.

        Returns:
            DetectionResult: Detected bounding boxes, labels, counts, latency, and metadata.

        TODO for Partner:
        -----------------
        1. Ensure model is loaded:
           if not self._is_loaded or self.model is None:
               raise RuntimeError("YoloDetector model is not loaded. Call load() first.")
        2. Measure inference time:
           import time
           start_time = time.perf_counter()
        3. Run inference directly on the RGB PIL image:
           results = self.model(image, conf=self.confidence_threshold)
        4. Parse Ultralytics results into BoundingBox and DetectedObject instances:
           detected_objects = []
           for r in results:
               boxes = r.boxes
               for box in boxes:
                   xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                   conf = float(box.conf[0])
                   cls_id = int(box.cls[0])
                   label = self.model.names.get(cls_id, str(cls_id))
                   detected_objects.append(
                       DetectedObject(
                           label=label,
                           confidence=round(conf, 4),
                           bbox=BoundingBox(
                               x1=round(xyxy[0], 2),
                               y1=round(xyxy[1], 2),
                               x2=round(xyxy[2], 2),
                               y2=round(xyxy[3], 2),
                           )
                       )
                   )
        5. Calculate elapsed milliseconds:
           inference_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        6. Return DetectionResult:
           return DetectionResult(
               objects=detected_objects,
               total_count=len(detected_objects),
               image_width=image.width,
               image_height=image.height,
               inference_ms=inference_ms,
               detector_name=self.name,
               extra={"weights": self.model_path},
           )
        """
        raise NotImplementedError(
            "YOLO detector detect() is not implemented yet. "
            "Implement detect() in app/services/detector/yolo_detector.py "
            "following the detailed TODO instructions."
        )

    def close(self) -> None:
        """Clean up model resources and GPU cache if applicable.

        TODO for Partner:
        -----------------
        If using CUDA:
           import torch
           if torch.cuda.is_available():
               torch.cuda.empty_cache()
        self.model = None
        self._is_loaded = False
        """
        self.model = None
        self._is_loaded = False
