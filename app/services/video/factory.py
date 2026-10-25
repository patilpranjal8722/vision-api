"""Frame reader factory function resolving video backend instances."""

from typing import Optional

from app.core.config import Settings, get_settings
from app.services.video.base import BaseFrameReader
from app.services.video.dummy import DummyFrameReader
from app.services.video.opencv_reader import OpenCVFrameReader

VALID_FRAME_READERS = ("dummy", "opencv")


def get_frame_reader(settings: Optional[Settings] = None) -> BaseFrameReader:
    """Instantiate and return the configured BaseFrameReader implementation.

    Args:
        settings: Application Settings instance. Defaults to get_settings().

    Returns:
        BaseFrameReader: Instantiated video frame reader (DummyFrameReader or OpenCVFrameReader).

    Raises:
        ValueError: If FRAME_READER_BACKEND is unrecognized.
    """
    if settings is None:
        settings = get_settings()

    backend = (settings.FRAME_READER_BACKEND or "").strip().lower()

    if backend == "dummy":
        return DummyFrameReader(delay_ms=settings.DUMMY_FRAME_DELAY_MS)
    elif backend == "opencv":
        return OpenCVFrameReader()
    else:
        raise ValueError(
            f"Invalid FRAME_READER_BACKEND '{settings.FRAME_READER_BACKEND}'. "
            f"Supported options are: {', '.join(VALID_FRAME_READERS)}."
        )
