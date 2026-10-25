"""Unit tests for video validation and container magic bytes detection."""

import io
from fastapi import HTTPException, UploadFile
import pytest

from app.services.video_service import detect_video_container, validate_and_save_video


def test_detect_video_container_mp4_and_mov() -> None:
    """Test magic bytes container detection for MP4 and QuickTime MOV."""
    # Standard MP4 container with 'ftypmp42'
    mp4_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00"
    assert detect_video_container(mp4_header) == "mp4"

    # QuickTime MOV container with 'ftypqt  '
    mov_header = b"\x00\x00\x00\x14ftypqt  \x20\x05\x03\x00"
    assert detect_video_container(mov_header) == "mov"


def test_detect_video_container_webm_and_avi() -> None:
    """Test magic bytes container detection for WebM/MKV and AVI."""
    # WebM / Matroska EBML signature
    webm_header = b"\x1a\x45\xdf\xa3\x93\x42\x82\x88matroska"
    assert detect_video_container(webm_header) == "webm"

    # AVI signature: 'RIFF....AVI '
    avi_header = b"RIFF\x24\x00\x00\x00AVI LIST\x00\x00\x00\x00"
    assert detect_video_container(avi_header) == "avi"


def test_detect_video_container_invalid_text_raises_400() -> None:
    """Test that text files or unrecognized byte sequences raise HTTP 400."""
    fake_header = b"This is just plain text content in a file named video.mp4"
    with pytest.raises(HTTPException) as exc_info:
        detect_video_container(fake_header)
    assert exc_info.value.status_code == 400
    assert "not a valid video file" in exc_info.value.detail.lower()


def test_validate_and_save_video_rejects_empty() -> None:
    """Test that empty video uploads are rejected with HTTP 400."""
    upload_file = UploadFile(
        file=io.BytesIO(b""),
        filename="empty.mp4",
        headers={"content-type": "video/mp4"},
    )
    with pytest.raises(HTTPException) as exc_info:
        validate_and_save_video(upload_file)
    assert exc_info.value.status_code == 400
    assert "empty" in exc_info.value.detail.lower()
