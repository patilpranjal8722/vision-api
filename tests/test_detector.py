"""Unit tests for BaseDetector, DummyDetector, YoloDetector, and detector factory."""

import io
import pytest
from PIL import Image

from app.core.config import Settings
from app.services.detector import (
    BaseDetector,
    DummyDetector,
    YoloDetector,
    get_detector,
)


def _make_image(width: int = 300, height: int = 200, color: str = "red") -> Image.Image:
    """Helper to generate an in-memory PIL RGB image."""
    return Image.new("RGB", (width, height), color=color)


def test_dummy_detector_lifecycle() -> None:
    """Test DummyDetector initial state, properties, and load lifecycle."""
    detector = DummyDetector(confidence_threshold=0.25)
    assert detector.name == "dummy"
    assert detector.is_placeholder is True
    assert detector.is_loaded is False

    # Calling detect before load must fail
    img = _make_image()
    with pytest.raises(RuntimeError, match="Detector is not loaded"):
        detector.detect(img)

    detector.load()
    assert detector.is_loaded is True

    # Calling detect after load succeeds
    result = detector.detect(img)
    assert result.detector_name == "dummy"

    # Teardown
    detector.close()
    assert detector.is_loaded is False


def test_dummy_detector_deterministic_results() -> None:
    """Test that the same image input produces the exact same detections."""
    detector = DummyDetector(confidence_threshold=0.20)
    detector.load()

    img = _make_image(width=400, height=300, color="green")

    res1 = detector.detect(img)
    res2 = detector.detect(img)

    assert res1.total_count == res2.total_count
    assert res1.image_width == 400
    assert res1.image_height == 300
    assert len(res1.objects) == len(res2.objects)

    for obj1, obj2 in zip(res1.objects, res2.objects):
        assert obj1.label == obj2.label
        assert obj1.confidence == obj2.confidence
        assert obj1.bbox.x1 == obj2.bbox.x1
        assert obj1.bbox.y1 == obj2.bbox.y1
        assert obj1.bbox.x2 == obj2.bbox.x2
        assert obj1.bbox.y2 == obj2.bbox.y2

    assert res1.extra == {"note": "placeholder detections, not real"}


def test_dummy_detector_bounding_boxes_in_bounds_and_valid() -> None:
    """Verify that every box stays inside the image bounds with x1 < x2 and y1 < y2."""
    detector = DummyDetector(confidence_threshold=0.10)
    detector.load()

    width, height = 500, 350
    img = _make_image(width=width, height=height, color="yellow")
    result = detector.detect(img)

    assert result.total_count == len(result.objects)

    for obj in result.objects:
        bbox = obj.bbox
        assert 0.0 <= bbox.x1 < bbox.x2 <= float(width), (
            f"Box x-coordinates invalid: x1={bbox.x1}, x2={bbox.x2}, width={width}"
        )
        assert 0.0 <= bbox.y1 < bbox.y2 <= float(height), (
            f"Box y-coordinates invalid: y1={bbox.y1}, y2={bbox.y2}, height={height}"
        )
        assert 0.30 <= obj.confidence <= 0.99


def test_dummy_detector_confidence_threshold_filtering() -> None:
    """Test that detections below the confidence threshold are excluded."""
    # Test with very high threshold that excludes detections
    detector_high = DummyDetector(confidence_threshold=0.9999)
    detector_high.load()

    img = _make_image(width=200, height=200, color="blue")
    result_high = detector_high.detect(img)

    assert result_high.total_count == len(result_high.objects)
    assert result_high.total_count == 0

    # Test with normal threshold
    detector_normal = DummyDetector(confidence_threshold=0.25)
    detector_normal.load()
    result_normal = detector_normal.detect(img)

    for obj in result_normal.objects:
        assert obj.confidence >= 0.25
    assert result_normal.total_count == len(result_normal.objects)


def test_yolo_detector_stub_raises_not_implemented() -> None:
    """Test that YoloDetector stub methods raise clear NotImplementedError."""
    yolo = YoloDetector()
    assert yolo.name == "yolo"
    assert yolo.is_placeholder is False
    assert yolo.is_loaded is False

    with pytest.raises(NotImplementedError, match="YOLO detector is not implemented yet"):
        yolo.load()

    img = _make_image()
    with pytest.raises(NotImplementedError, match="YOLO detector detect\\(\\) is not implemented"):
        yolo.detect(img)


def test_detector_factory_dummy_backend() -> None:
    """Test factory returns DummyDetector for backend 'dummy'."""
    settings = Settings(DETECTOR_BACKEND="dummy", SECRET_KEY="test-secret")
    detector = get_detector(settings)
    assert isinstance(detector, DummyDetector)
    assert detector.name == "dummy"


def test_detector_factory_yolo_backend() -> None:
    """Test factory returns YoloDetector for backend 'yolo'."""
    settings = Settings(DETECTOR_BACKEND="yolo", SECRET_KEY="test-secret")
    detector = get_detector(settings)
    assert isinstance(detector, YoloDetector)
    assert detector.name == "yolo"


def test_detector_factory_unknown_backend_raises_error() -> None:
    """Test factory raises clear ValueError for unsupported backends listing valid options."""
    settings = Settings(DETECTOR_BACKEND="unsupported_backend", SECRET_KEY="test-secret")
    with pytest.raises(ValueError) as exc_info:
        get_detector(settings)

    err_msg = str(exc_info.value)
    assert "Invalid DETECTOR_BACKEND 'unsupported_backend'" in err_msg
    assert "dummy" in err_msg
    assert "yolo" in err_msg
