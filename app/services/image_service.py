"""Image validation, decoding, and secure storage service."""

import io
from pathlib import Path
from typing import Optional, Tuple
import uuid
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.core.config import Settings, get_settings

# Mapping Pillow format names to standardized file extensions
FORMAT_TO_EXTENSION = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}

CHUNK_SIZE = 64 * 1024  # 64 KB read buffer


def validate_and_save_image(
    file: UploadFile,
    settings: Optional[Settings] = None,
) -> Tuple[Image.Image, str]:
    """Validate an uploaded image file, decode it to RGB, and securely persist it.

    Enforces strict upload security controls:
    1. Rejects content types not present in ALLOWED_IMAGE_TYPES with HTTP 415.
    2. Streams upload in chunks; aborts with HTTP 413 immediately when file exceeds MAX_UPLOAD_MB.
    3. Rejects empty uploads with HTTP 400.
    4. Verifies byte stream with Pillow (img.verify()), then reopens and converts to RGB.
    5. Rejects undecodable files and decompression bombs with HTTP 400.
    6. Rejects images exceeding MAX_IMAGE_DIMENSION with HTTP 400.
    7. Resolves file extension strictly from detected Pillow format, ignoring client filename.
    8. Writes original bytes to UPLOAD_DIR/images/<uuid4>.<ext>, creating parent folders if absent.

    Args:
        file: FastAPI UploadFile object.
        settings: Application Settings instance. Defaults to get_settings().

    Returns:
        Tuple[Image.Image, str]: The decoded RGB PIL Image and the saved relative file path.

    Raises:
        HTTPException 400: If file is empty, corrupted, exceeds dimension, or bomb error.
        HTTPException 413: If file size exceeds MAX_UPLOAD_MB.
        HTTPException 415: If MIME type is not allowed.
    """
    if settings is None:
        settings = get_settings()

    # 1. Content-Type Header Validation
    content_type = (file.content_type or "").lower().strip()
    allowed_types = [t.lower().strip() for t in settings.ALLOWED_IMAGE_TYPES]
    if not content_type or content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported media type: '{file.content_type}'. "
                f"Allowed types: {', '.join(settings.ALLOWED_IMAGE_TYPES)}"
            ),
        )

    # 2. Chunked stream reading with immediate 413 cutoff
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    file_bytes = bytearray()
    total_bytes = 0

    while True:
        chunk = file.file.read(CHUNK_SIZE)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File size exceeds maximum allowed upload limit of {settings.MAX_UPLOAD_MB} MB",
            )
        file_bytes.extend(chunk)

    # 3. Reject empty files
    if total_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # 4. Verify integrity with Pillow (verify then reopen)
    try:
        buffer = io.BytesIO(file_bytes)
        with Image.open(buffer) as img:
            img.verify()
            detected_format = img.format
    except Image.DecompressionBombError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image exceeds safe decompression limits: {exc}",
        )
    except (UnidentifiedImageError, Exception):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or undecodable image file",
        )

    if not detected_format or detected_format.upper() not in FORMAT_TO_EXTENSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image encoding format: '{detected_format}'",
        )

    # Reopen to read dimensions and convert to RGB
    try:
        buffer.seek(0)
        img_reopened = Image.open(buffer)
        width, height = img_reopened.size

        # 5. Check dimensions
        if width > settings.MAX_IMAGE_DIMENSION or height > settings.MAX_IMAGE_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Image dimensions ({width}x{height}) exceed maximum allowed dimension "
                    f"of {settings.MAX_IMAGE_DIMENSION}px"
                ),
            )

        rgb_image = img_reopened.convert("RGB")
    except HTTPException:
        raise
    except Image.DecompressionBombError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image exceeds safe decompression limits: {exc}",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decode image data into RGB",
        )

    # 6. Save original bytes with UUID filename (client filename ignored)
    ext = FORMAT_TO_EXTENSION[detected_format.upper()]
    unique_filename = f"{uuid.uuid4()}.{ext}"
    dest_dir = Path(settings.UPLOAD_DIR) / "images"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / unique_filename
    dest_path.write_bytes(file_bytes)

    # Store normalized posix path in database
    saved_path_str = dest_path.as_posix()

    return rgb_image, saved_path_str
