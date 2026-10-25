"""Unit tests for video frame readers and factory."""

from pathlib import Path
import pytest
from PIL import Image

from app.core.config import Settings
from app.services.video import (
    BaseFrameReader,
    DummyFrameReader,
    OpenCVFrameReader,
    get_frame_reader,
)


def test_dummy_frame_reader_properties_and_lifecycle(tmp_path: Path) -> None:
    """Test DummyFrameReader metadata, derived frame counts, and context manager."""
    dummy_file = tmp_path / "sample.mp4"
    dummy_file.write_bytes(b"\x00" * 500)

    reader = DummyFrameReader(delay_ms=0)
    assert reader.fps == 25.0
    assert reader.width == 640
    assert reader.height == 480

    with reader.open(str(dummy_file)) as capture:
        assert capture.total_frames >= 60
        assert capture.total_frames <= 300
        assert capture.fps == 25.0

        frames = list(capture.iter_frames(frame_skip=10))
        assert len(frames) > 0

        # Verify frame tuple structure: (index, timestamp_seconds, PIL.Image in RGB)
        first_idx, first_time, first_img = frames[0]
        assert first_idx == 0
        assert first_time == 0.0
        assert isinstance(first_img, Image.Image)
        assert first_img.mode == "RGB"
        assert first_img.size == (640, 480)


def test_dummy_frame_reader_respects_frame_skip(tmp_path: Path) -> None:
    """Verify that iter_frames honors different frame_skip values."""
    dummy_file = tmp_path / "sample.mp4"
    dummy_file.write_bytes(b"\x00" * 1000)

    reader = DummyFrameReader(delay_ms=0)
    with reader.open(str(dummy_file)) as capture:
        total = capture.total_frames
        skip_5 = list(capture.iter_frames(frame_skip=5))
        skip_20 = list(capture.iter_frames(frame_skip=20))

        assert len(skip_5) > len(skip_20)
        # Check indices are spaced by frame_skip
        assert skip_5[1][0] == 5
        assert skip_20[1][0] == 20


def test_opencv_reader_stub_raises_not_implemented() -> None:
    """Test that OpenCVFrameReader stub methods raise clear NotImplementedError."""
    reader = OpenCVFrameReader()

    with pytest.raises(NotImplementedError, match="OpenCVFrameReader is not implemented yet"):
        reader.open("path/to/video.mp4")

    with pytest.raises(NotImplementedError):
        _ = reader.fps

    with pytest.raises(NotImplementedError):
        _ = reader.total_frames

    with pytest.raises(NotImplementedError):
        _ = reader.width

    with pytest.raises(NotImplementedError):
        _ = reader.height

    with pytest.raises(NotImplementedError):
        list(reader.iter_frames())


def test_frame_reader_factory() -> None:
    """Test factory resolution for supported and unsupported backends."""
    dummy_settings = Settings(FRAME_READER_BACKEND="dummy", SECRET_KEY="test-secret")
    assert isinstance(get_frame_reader(dummy_settings), DummyFrameReader)

    cv_settings = Settings(FRAME_READER_BACKEND="opencv", SECRET_KEY="test-secret")
    assert isinstance(get_frame_reader(cv_settings), OpenCVFrameReader)

    invalid_settings = Settings(FRAME_READER_BACKEND="unknown_reader", SECRET_KEY="test-secret")
    with pytest.raises(ValueError, match="Invalid FRAME_READER_BACKEND 'unknown_reader'"):
        get_frame_reader(invalid_settings)
