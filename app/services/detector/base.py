"""Base abstract detector class defining the computer vision model interface."""

from abc import ABC, abstractmethod
from PIL import Image

from app.schemas.detection import DetectionResult


class BaseDetector(ABC):
    """Abstract base class for all computer vision object detector backends.

    This interface guarantees that swapping out mock models for real deep learning
    architectures (e.g., Ultralytics YOLO, Faster R-CNN, RT-DETR) requires zero
    modifications to API routing, file storage, or database persistence.
    """

    name: str = "base"
    _is_loaded: bool = False

    @property
    def is_placeholder(self) -> bool:
        """Indicate whether this detector is a mock/placeholder implementation.

        Returns:
            bool: False by default for real production detector models.
        """
        return False

    @property
    def is_loaded(self) -> bool:
        """Check if model weights and resources are loaded into memory.

        Returns:
            bool: True if loaded successfully, False otherwise.
        """
        return self._is_loaded

    def load(self) -> None:
        """Load model weights or computational graphs into memory/GPU.

        Executed once at application startup during the FastAPI lifespan event.
        Subclasses should override this method to load weights from disk.
        """
        self._is_loaded = True

    @abstractmethod
    def detect(self, image: Image.Image) -> DetectionResult:
        """Run object detection inference on a decoded PIL Image.

        Args:
            image: A decoded PIL.Image.Image object guaranteed to be in 'RGB' color mode.

        Partner Integration Guidance (for OpenCV / NumPy workflows):
            If your pipeline requires OpenCV (cv2) or NumPy array representations:
            ```python
            import numpy as np
            import cv2

            # 1. Convert the PIL Image to an RGB NumPy array:
            rgb_array = np.array(image)

            # 2. Convert RGB to BGR for OpenCV functions:
            bgr_image = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)

            # 3. For Ultralytics YOLO, the model directly accepts PIL Images:
            # results = self.model(image)
            ```

        Returns:
            DetectionResult: Validated Pydantic schema containing detected objects,
            bounding box coordinates, total count, latency in milliseconds,
            and model metadata.
        """
        pass

    def close(self) -> None:
        """Release GPU memory, file handles, or background threads on server shutdown.

        Defaults to a no-op; subclasses may override if explicit teardown is needed.
        """
        pass
