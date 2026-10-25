"""Abstract base class for video frame readers."""

from abc import ABC, abstractmethod
from typing import Generator, Tuple
from PIL import Image


class BaseFrameReader(ABC):
    """Abstract video frame reader providing sequential access to RGB PIL Images.

    This abstraction decouples video container parsing and frame extraction from
    downstream model inference, enabling lightweight simulated readers during
    development and drop-in OpenCV/FFmpeg decoders in production.

    Usage as a context manager:
    ```python
    with get_frame_reader().open(video_path) as reader:
        for frame_idx, timestamp_s, pil_image in reader.iter_frames(frame_skip=5):
            results = detector.detect(pil_image)
    ```

    Partner Integration Guidance (for OpenCV cv2.VideoCapture):
    -----------------------------------------------------------
    To implement a real decoder using OpenCV in `opencv_reader.py`:
    ```python
    import cv2
    from PIL import Image

    # 1. Open the video file
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {path}")

    # 2. Extract container metadata
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 3. Iterate frames respecting frame_skip
    frame_idx = 0
    while cap.isOpened():
        ret, bgr_frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_skip == 0:
            # Convert OpenCV BGR array to RGB array
            rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            # Wrap array in PIL Image without copying buffer
            pil_image = Image.fromarray(rgb_frame)
            timestamp = frame_idx / fps
            yield (frame_idx, timestamp, pil_image)
        frame_idx += 1

    # 4. Release native handles in close()
    cap.release()
    ```
    """

    @abstractmethod
    def open(self, path: str) -> "BaseFrameReader":
        """Open a video file from disk and parse stream properties."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Release underlying video capture handles, decoders, or memory maps."""
        pass

    def __enter__(self) -> "BaseFrameReader":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Exit context manager and close frame reader."""
        self.close()

    @property
    @abstractmethod
    def fps(self) -> float:
        """Frame rate in frames per second."""
        pass

    @property
    @abstractmethod
    def total_frames(self) -> int:
        """Total frame count in the video stream."""
        pass

    @property
    @abstractmethod
    def width(self) -> int:
        """Horizontal frame resolution in pixels."""
        pass

    @property
    @abstractmethod
    def height(self) -> int:
        """Vertical frame resolution in pixels."""
        pass

    @abstractmethod
    def iter_frames(
        self, frame_skip: int = 1
    ) -> Generator[Tuple[int, float, Image.Image], None, None]:
        """Yield sequential sampled video frames.

        Args:
            frame_skip: Interval between processed frames (e.g. 1 processes every frame,
                5 processes frames 0, 5, 10, ...).

        Yields:
            Tuple[int, float, Image.Image]: (frame_index, timestamp_seconds, pil_rgb_image).
        """
        pass
