"""Simulated frame reader returning synthetic video frames without native decoders."""

import os
import time
from typing import Generator, Optional, Tuple
from PIL import Image

from app.core.config import get_settings
from app.services.video.base import BaseFrameReader


class DummyFrameReader(BaseFrameReader):
    """Simulated video frame reader for development and automated testing.

    Requires zero GPU, FFmpeg, or OpenCV libraries. Simulates video playback
    by generating solid-color RGB PIL images and sleeping briefly between frames.
    The number of frames is deterministically derived from the target file size.
    """

    def __init__(self, delay_ms: Optional[int] = None) -> None:
        settings = get_settings()
        self.delay_ms = (
            delay_ms if delay_ms is not None else settings.DUMMY_FRAME_DELAY_MS
        )
        self._path: Optional[str] = None
        self._total_frames: int = 120
        self._fps: float = 25.0
        self._width: int = 640
        self._height: int = 480
        self._is_open: bool = False

    def open(self, path: str) -> "DummyFrameReader":
        """Simulate opening a video file, deriving frame count from file size."""
        self._path = path
        file_size = 0
        if os.path.exists(path):
            try:
                file_size = os.path.getsize(path)
            except OSError:
                file_size = 0

        # Derive total frames between 60 and 300 based on file size
        # Uses modulo hash to maintain stable frame counts for identical files
        span = 300 - 60
        derived = 60 + (file_size % span)
        self._total_frames = max(60, min(300, derived))
        self._fps = 25.0
        self._width = 640
        self._height = 480
        self._is_open = True
        return self

    def close(self) -> None:
        """Close reader session."""
        self._is_open = False

    @property
    def fps(self) -> float:
        """Simulated frame rate (25.0 fps)."""
        return self._fps

    @property
    def total_frames(self) -> int:
        """Total simulated frame count (between 60 and 300)."""
        return self._total_frames

    @property
    def width(self) -> int:
        """Simulated width (640px)."""
        return self._width

    @property
    def height(self) -> int:
        """Simulated height (480px)."""
        return self._height

    def iter_frames(
        self, frame_skip: int = 1
    ) -> Generator[Tuple[int, float, Image.Image], None, None]:
        """Yield simulated frames respecting frame_skip.

        Args:
            frame_skip: Sample stride (1 <= frame_skip <= total_frames).

        Yields:
            Tuple[int, float, Image.Image]: (frame_index, timestamp_seconds, pil_rgb_image).
        """
        if not self._is_open:
            raise RuntimeError("DummyFrameReader is not open. Call open() first.")

        stride = max(1, frame_skip)
        delay_seconds = max(0.0, self.delay_ms / 1000.0)

        for frame_idx in range(0, self._total_frames, stride):
            if delay_seconds > 0:
                time.sleep(delay_seconds)

            timestamp_s = round(frame_idx / self._fps, 3)

            # Generate varying solid RGB color based on frame index
            r = (frame_idx * 17) % 256
            g = (frame_idx * 29 + 60) % 256
            b = (frame_idx * 43 + 120) % 256
            frame_image = Image.new("RGB", (self._width, self._height), color=(r, g, b))

            yield frame_idx, timestamp_s, frame_image
