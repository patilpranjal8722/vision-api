"""Video frame reader package and factory."""

from app.services.video.base import BaseFrameReader
from app.services.video.dummy import DummyFrameReader
from app.services.video.factory import get_frame_reader
from app.services.video.opencv_reader import OpenCVFrameReader

__all__ = [
    "BaseFrameReader",
    "DummyFrameReader",
    "OpenCVFrameReader",
    "get_frame_reader",
]
