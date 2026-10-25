"""Video upload validation, container signature verification, and secure storage service."""

from pathlib import Path
from typing import Optional
import uuid
from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings, get_settings

CHUNK_SIZE = 64 * 1024  # 64 KB streaming buffer


def detect_video_container(header: bytes) -> str:
    """Detect video container format and return file extension from magic bytes.

    Container Signature Rules:
    - MP4 / MOV: 'ftyp' at bytes 4 to 8. If major brand (bytes 8 to 12) is 'qt  ',
      the extension is 'mov'; otherwise 'mp4'.
    - WebM / MKV: Starts with bytes 1A 45 DF A3 (extension 'webm').
    - AVI: Starts with 'RIFF' (bytes 0 to 4) and contains 'AVI ' at bytes 8 to 12
      (extension 'avi').

    Note:
        This is a container signature check only; full decode validation belongs
        to the OpenCV reader when reading frames.

    Args:
        header: Raw initial bytes of the video file (at least 12 bytes).

    Returns:
        str: Detected file extension ('mp4', 'mov', 'webm', or 'avi').

    Raises:
        HTTPException 400: If the byte signature does not match any allowed container.
    """
    if len(header) >= 8 and header[4:8] == b"ftyp":
        brand = header[8:12] if len(header) >= 12 else b""
        if brand == b"qt  ":
            return "mov"
        return "mp4"

    if len(header) >= 4 and header[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"

    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"AVI ":
        return "avi"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Not a valid video file",
    )


def validate_and_save_video(
    file: UploadFile,
    settings: Optional[Settings] = None,
) -> str:
    """Validate uploaded video, detect container, and stream directly to disk.

    Security & Validation Controls:
    1. Rejects MIME types not present in ALLOWED_VIDEO_TYPES with HTTP 415.
    2. Rejects empty files with HTTP 400.
    3. Verifies container magic bytes; rejects unknown signatures with HTTP 400.
    4. Streams directly to disk in chunks; aborts immediately with HTTP 413 if
       file size exceeds MAX_VIDEO_UPLOAD_MB, deleting any partial file.
    5. Resolves extension strictly from container magic bytes, ignoring client filename.
    6. Saves file to UPLOAD_DIR/videos/<uuid4>.<ext>.

    Args:
        file: UploadFile from FastAPI request.
        settings: Application Settings instance. Defaults to get_settings().

    Returns:
        str: Relative POSIX path to the saved video file.

    Raises:
        HTTPException 400: If empty file or invalid video container signature.
        HTTPException 413: If upload exceeds MAX_VIDEO_UPLOAD_MB.
        HTTPException 415: If MIME type is not allowed.
    """
    if settings is None:
        settings = get_settings()

    # 1. Content-Type Header Validation
    content_type = (file.content_type or "").lower().strip()
    allowed_types = [t.lower().strip() for t in settings.ALLOWED_VIDEO_TYPES]
    if not content_type or content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported media type: '{file.content_type}'. "
                f"Allowed types: {', '.join(settings.ALLOWED_VIDEO_TYPES)}"
            ),
        )

    # 2. Read first chunk for empty check and container magic bytes detection
    first_chunk = file.file.read(CHUNK_SIZE)
    if not first_chunk or len(first_chunk) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    max_bytes = settings.MAX_VIDEO_UPLOAD_MB * 1024 * 1024
    if len(first_chunk) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File size exceeds maximum allowed upload limit of {settings.MAX_VIDEO_UPLOAD_MB} MB",
        )

    # 3. Detect container and determine file extension
    ext = detect_video_container(first_chunk)

    # 4. Prepare target path with UUID filename
    unique_filename = f"{uuid.uuid4()}.{ext}"
    dest_dir = Path(settings.UPLOAD_DIR) / "videos"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / unique_filename

    total_bytes = len(first_chunk)

    try:
        with open(dest_path, "wb") as out_f:
            out_f.write(first_chunk)
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=(
                            f"File size exceeds maximum allowed upload limit of "
                            f"{settings.MAX_VIDEO_UPLOAD_MB} MB"
                        ),
                    )
                out_f.write(chunk)
    except Exception:
        # Clean up partial file on any exception
        if dest_path.exists():
            try:
                dest_path.unlink()
            except OSError:
                pass
        raise

    return dest_path.as_posix()
