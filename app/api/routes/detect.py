import mimetypes
from pathlib import Path
import re
from typing import List, Optional
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.detection import Detection
from app.models.job import Job
from app.models.user import User
from app.schemas.detection import DetectionOut
from app.schemas.job import JobSubmitOut
from app.schemas.ppe import (
    DetectConfigOut,
    DetectorConfigOut,
    ORDERED_EQUIPMENT,
    PpeConfigOut,
    UploadConfigOut,
)
from app.services.image_service import validate_and_save_image
from app.services.inference import InferenceTimeout, ServerBusy, run_inference
from app.services.ppe_rules import (
    InvalidDetectorOutput,
    apply_rules,
    parse_required_equipment,
    validate_detector_output,
)
from app.services.video_service import validate_and_save_video

router = APIRouter(prefix="/detect", tags=["Detection"])
logger = get_logger("vision_api.detect")

CAMERA_NAME_REGEX = re.compile(r"^[a-zA-Z0-9 _.-]+$")


@router.post(
    "/video",
    response_model=JobSubmitOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload video and submit background detection job",
)
@limiter.limit(lambda: get_settings().UPLOAD_RATE_LIMIT)
def detect_video(
    request: Request,
    file: UploadFile = File(...),
    frame_skip: Optional[int] = Query(
        default=None,
        ge=1,
        le=60,
        description="Sampling stride in frames (1 to 60; defaults to FRAME_SKIP)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JobSubmitOut:
    """Upload a video file and submit an asynchronous detection job.

    - Validates MIME type, streaming file size limit (HTTP 413), and container magic bytes.
    - Saves video under UUID filename in UPLOAD_DIR/videos/.
    - Returns HTTP 503 if detector is not loaded/available.
    - Limits active (pending/running) jobs per user to MAX_ACTIVE_JOBS_PER_USER (HTTP 429).
    - Submits job to ThreadPoolExecutor (or processes inline if JOB_RUNNER_INLINE is True).
    - Cleans up orphan uploaded video file if database insertion fails.
    - Returns HTTP 202 Accepted with {job_id, status, progress, created_at}.
    """
    detector = getattr(request.app.state, "detector", None)
    if detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Detector not available",
        )

    # Check active jobs limit for current user
    active_jobs_count = (
        db.query(Job)
        .filter(
            Job.user_id == current_user.id,
            Job.status.in_(["pending", "running"]),
        )
        .count()
    )
    if active_jobs_count >= settings.MAX_ACTIVE_JOBS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Active job limit reached. You currently have {active_jobs_count} "
                f"active jobs (maximum allowed is {settings.MAX_ACTIVE_JOBS_PER_USER}). "
                f"Please wait for pending or running jobs to complete."
            ),
        )

    # 1. Validate video container and save to disk
    saved_video_path = validate_and_save_video(file, settings=settings)

    # 2. Create Job entity with orphan cleanup protection
    try:
        actual_frame_skip = frame_skip if frame_skip is not None else settings.FRAME_SKIP
        job = Job(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            type="video",
            status="pending",
            progress=0,
            input_path=saved_video_path,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # 3. Submit to job runner
        runner = getattr(request.app.state, "job_runner", None)
        if runner is not None:
            runner.submit(job.id, frame_skip=actual_frame_skip)
        else:
            from app.services.job_runner import JobRunner

            fallback_runner = JobRunner(request.app, settings)
            fallback_runner.submit(job.id, frame_skip=actual_frame_skip)
    except Exception:
        # Prevent orphan video upload file if database commit or enqueueing fails
        try:
            Path(saved_video_path).unlink(missing_ok=True)
        except Exception:
            pass
        raise

    return JobSubmitOut(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
    )


@router.post(
    "/image",
    response_model=DetectionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload image and perform object detection",
)
@limiter.limit(lambda: get_settings().UPLOAD_RATE_LIMIT)
async def detect_image(
    request: Request,
    file: UploadFile = File(...),
    required_equipment: Optional[str] = Form(default=None),
    camera_name: Optional[str] = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Detection:
    """Upload an image file, validate dimensions/format, run detection, and save results.

    - Validates MIME type, file size (streaming 413 cutoff), and Pillow image decoding.
    - Accepts optional multipart form fields: required_equipment and camera_name.
    - Saves image to disk under a generated UUID filename in UPLOAD_DIR/images/.
    - Returns 503 if detector is not loaded/available.
    - Runs inference via run_inference() protecting against queue saturation (503) and timeout (504).
    - If detector returns PPE schema ('ppe.v1'), runs validate_detector_output and apply_rules.
    - Cleans up orphan uploaded image file if inference or database commit fails.
    - Persists detection metadata, counts, and bounding box JSON in the database.
    """
    detector = getattr(request.app.state, "detector", None)
    if detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Detector not available",
        )

    # Validate required_equipment parameter (distinguish omitted from explicitly empty string)
    form_data = await request.form()
    if "required_equipment" in form_data:
        raw_eq_val = form_data.get("required_equipment")
        if raw_eq_val is None or (isinstance(raw_eq_val, str) and not raw_eq_val.strip()):
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("body", "required_equipment"),
                        "msg": "Required equipment cannot be empty. Valid options are: helmet, vest.",
                        "input": raw_eq_val,
                    }
                ]
            )
        try:
            parsed_required = parse_required_equipment(str(raw_eq_val))
        except ValueError as exc:
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("body", "required_equipment"),
                        "msg": str(exc),
                        "input": raw_eq_val,
                    }
                ]
            )
    else:
        try:
            parsed_required = parse_required_equipment(default=settings.DEFAULT_REQUIRED_EQUIPMENT)
        except ValueError as exc:
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("body", "required_equipment"),
                        "msg": str(exc),
                        "input": None,
                    }
                ]
            )

    # Validate camera_name parameter
    parsed_camera_name: Optional[str] = None
    if camera_name is not None:
        trimmed_cam = camera_name.strip()
        if trimmed_cam:
            if len(trimmed_cam) > settings.CAMERA_NAME_MAX_LENGTH:
                raise RequestValidationError(
                    [
                        {
                            "type": "string_too_long",
                            "loc": ("body", "camera_name"),
                            "msg": f"camera_name cannot exceed {settings.CAMERA_NAME_MAX_LENGTH} characters.",
                            "input": camera_name,
                        }
                    ]
                )
            if not CAMERA_NAME_REGEX.match(trimmed_cam):
                raise RequestValidationError(
                    [
                        {
                            "type": "string_pattern_mismatch",
                            "loc": ("body", "camera_name"),
                            "msg": "camera_name may only contain letters, digits, space, dash, underscore, and dot.",
                            "input": camera_name,
                        }
                    ]
                )
            parsed_camera_name = trimmed_cam

    # 1. Validate, decode to RGB, and persist upload to disk off the event loop
    rgb_image, file_path = await run_in_threadpool(
        validate_and_save_image, file, settings=settings
    )

    try:
        # 2. Run object detection inference safely with timeout & concurrency controls
        try:
            detection_result = await run_inference(detector, rgb_image)
        except ServerBusy as exc:
            logger.warning(f"Inference queue saturated: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Server busy, try again shortly",
            )
        except InferenceTimeout as exc:
            logger.warning(f"Inference execution timed out: {exc}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Inference timeout",
            )
        except Exception as exc:
            logger.error(f"Inference execution failed: {exc}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Detection inference failed",
            )

        # 3. If detector returned PPE schema, validate and apply compliance rules
        if (
            isinstance(detection_result.extra, dict)
            and detection_result.extra.get("schema") == "ppe.v1"
        ):
            try:
                validate_detector_output(detection_result, rgb_image.width, rgb_image.height)
            except InvalidDetectorOutput as exc:
                logger.error(f"Detector returned an invalid result: {exc}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Detector returned an invalid result",
                )
            detection_result = apply_rules(
                detection_result,
                required=parsed_required,
                camera_name=parsed_camera_name,
            )

        # 4. Store Detection record in database
        detection_record = Detection(
            user_id=current_user.id,
            source_type="image",
            file_path=file_path,
            detector_name=detection_result.detector_name,
            total_count=detection_result.total_count,
            results=detection_result.model_dump(),
        )
        db.add(detection_record)
        db.commit()
        db.refresh(detection_record)
    except Exception:
        # Clean up uploaded image on disk if inference or database saving fails (no orphan uploads)
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass
        raise

    # 5. Evaluate alerts (non-blocking for image detection failure)
    try:
        from app.services.alert_service import evaluate_detection

        evaluate_detection(db, detection_record)
    except Exception as exc:
        logger.error(
            f"Alert evaluation failed for detection {detection_record.id}: {exc}",
            exc_info=True,
        )

    return detection_record


@router.get(
    "/history",
    response_model=List[DetectionOut],
    summary="List detection history with pagination",
)
def get_detection_history(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Detection]:
    """Retrieve detection records ordered newest first.

    - Standard users only see their own detections.
    - Administrators can view all system detection records.
    """
    query = db.query(Detection)
    if current_user.role != "admin":
        query = query.filter(Detection.user_id == current_user.id)

    offset = (page - 1) * limit
    detections = (
        query.order_by(Detection.created_at.desc(), Detection.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return detections


@router.get(
    "/config",
    response_model=DetectConfigOut,
    summary="Retrieve detection pipeline and PPE configuration",
)
def get_detect_config(
    request: Request,
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DetectConfigOut:
    """Retrieve active detector backend status, PPE equipment rules, and upload limits.

    Declared before /{detection_id} so the string 'config' is never parsed as a numeric ID.
    Requires authentication.
    """
    detector = getattr(request.app.state, "detector", None)
    if detector is not None:
        det_name = detector.name
        is_placeholder = detector.is_placeholder
        loaded = detector.is_loaded
    else:
        det_name = settings.DETECTOR_BACKEND
        is_placeholder = True
        loaded = False

    allowed_images = (
        settings.ALLOWED_IMAGE_TYPES
        if isinstance(settings.ALLOWED_IMAGE_TYPES, list)
        else [t.strip() for t in settings.ALLOWED_IMAGE_TYPES.split(",") if t.strip()]
    )
    allowed_videos = (
        settings.ALLOWED_VIDEO_TYPES
        if isinstance(settings.ALLOWED_VIDEO_TYPES, list)
        else [t.strip() for t in settings.ALLOWED_VIDEO_TYPES.split(",") if t.strip()]
    )

    try:
        default_req = parse_required_equipment(settings.DEFAULT_REQUIRED_EQUIPMENT)
    except Exception:
        default_req = ["helmet", "vest"]

    return DetectConfigOut(
        detector=DetectorConfigOut(
            name=det_name,
            is_placeholder=is_placeholder,
            loaded=loaded,
        ),
        ppe=PpeConfigOut(
            schema="ppe.v1",
            supported_equipment=list(ORDERED_EQUIPMENT),
            default_required_equipment=default_req,
        ),
        upload=UploadConfigOut(
            max_image_mb=settings.MAX_UPLOAD_MB,
            allowed_image_types=allowed_images,
            max_image_dimension=settings.MAX_IMAGE_DIMENSION,
            max_video_mb=settings.MAX_VIDEO_UPLOAD_MB,
            allowed_video_types=allowed_videos,
        ),
        confidence_threshold=settings.CONFIDENCE_THRESHOLD,
    )


@router.get(
    "/{detection_id}/image",
    summary="Download original image for a detection",
)
def get_detection_image(
    detection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Retrieve the original uploaded image file associated with a detection record.

    - Only accessible to the record owner or administrators (404 otherwise).
    - Checks path traversal containment within UPLOAD_DIR.
    - Sets Cache-Control: private, max-age=300.
    """
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection not found",
        )

    if current_user.role != "admin" and detection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection not found",
        )

    if detection.source_type != "image" or not detection.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found for this detection",
        )

    stored_path = Path(detection.file_path).resolve()
    upload_dir = Path(settings.UPLOAD_DIR).resolve()

    try:
        stored_path.relative_to(upload_dir)
    except ValueError:
        logger.warning(
            f"Path containment violation: stored path '{stored_path}' is outside '{upload_dir}'"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found",
        )

    if not stored_path.exists() or not stored_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found",
        )

    media_type, _ = mimetypes.guess_type(str(stored_path))
    if not media_type or not media_type.startswith("image/"):
        media_type = "image/jpeg"

    return FileResponse(
        path=str(stored_path),
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get(
    "/{detection_id}",
    response_model=DetectionOut,
    summary="Retrieve a specific detection by ID",
)
def get_detection_by_id(
    detection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Detection:
    """Retrieve a single detection record by its database ID.

    - Accessible if the record belongs to the requesting user or if user is an admin.
    - Returns 404 if not found or unauthorized to prevent disclosing record existence.
    """
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection not found",
        )

    if current_user.role != "admin" and detection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection not found",
        )

    return detection
