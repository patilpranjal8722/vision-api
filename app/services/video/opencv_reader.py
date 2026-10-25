"""OpenCV VideoCapture frame reader stub for future partner implementation."""

from typing import Generator, Optional, Tuple
from PIL import Image

from app.services.video.base import BaseFrameReader


class OpenCVFrameReader(BaseFrameReader):
    """Real video frame reader using OpenCV VideoCapture.

    IMPORTANT FOR DEVELOPERS & PARTNERS:
    -----------------------------------
    Do NOT import cv2 or numpy at module top-level!
    All ML/CV dependencies must be lazily imported inside methods (such as open())
    so that the lightweight FastAPI template can boot and run without OpenCV installed.
    """

    def __init__(self) -> None:
        self._path: Optional[str] = None
        self._cap = None
        self._fps: float = 0.0
        self._total_frames: int = 0
        self._width: int = 0
        self._height: int = 0

    def open(self, path: str) -> "OpenCVFrameReader":
        """Open video file via cv2.VideoCapture.

        TODO for Partner:
        -----------------
        1. Install requirements-cv.txt:
           pip install -r requirements-cv.txt
        2. Lazily import cv2 inside this method:
           import cv2
        3. Initialize capture object:
           self._cap = cv2.VideoCapture(path)
           if not self._cap.isOpened():
               raise ValueError(f"OpenCV failed to open video file: {path}")
        4. Populate stream metadata:
           self._fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 25.0)
           self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
           self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
           self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
           self._path = path
           return self
        """
        raise NotImplementedError(
            "OpenCVFrameReader is not implemented yet. "
            "Install requirements-cv.txt, set FRAME_READER_BACKEND=opencv in .env, "
            "and implement open(), close(), and iter_frames() in app/services/video/opencv_reader.py."
        )

    def close(self) -> None:
        """Release native OpenCV capture handle.

        TODO for Partner:
        -----------------
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        """
        if self._cap is not None:
            self._cap = None

    @property
    def fps(self) -> float:
        """Video frames per second."""
        raise NotImplementedError("OpenCVFrameReader metadata is not available until implemented.")

    @property
    def total_frames(self) -> int:
        """Total frame count."""
        raise NotImplementedError("OpenCVFrameReader metadata is not available until implemented.")

    @property
    def width(self) -> int:
        """Video pixel width."""
        raise NotImplementedError("OpenCVFrameReader metadata is not available until implemented.")

    @property
    def height(self) -> int:
        """Video pixel height."""
        raise NotImplementedError("OpenCVFrameReader metadata is not available until implemented.")

    def iter_frames(
        self, frame_skip: int = 1
    ) -> Generator[Tuple[int, float, Image.Image], None, None]:
        """Read and decode sequential video frames into RGB PIL Images.

        TODO for Partner:
        -----------------
        1. Import cv2:
           import cv2
        2. Iterate over capture frames:
           frame_idx = 0
           while self._cap and self._cap.isOpened():
               ret, bgr_frame = self._cap.read()
               if not ret:
                   break
               if frame_idx % frame_skip == 0:
                   rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                   pil_image = Image.fromarray(rgb_frame)
                   timestamp = frame_idx / self._fps
                   yield frame_idx, timestamp, pil_image
               frame_idx += 1
        """
        raise NotImplementedError(
            "OpenCVFrameReader iter_frames() is not implemented yet. "
            "Follow the detailed TODO instructions in app/services/video/opencv_reader.py."
        )
