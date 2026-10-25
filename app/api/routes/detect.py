from pathlib import Path
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

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
from app.services.image_service import validate_and_save_image
from app.services.inference import InferenceTimeout, ServerBusy, run_inference
from app.services.video_service import validate_and_save_video

router = APIRouter(prefix="/detect", tags=["Detection"])
logger = get_logger("vision_api.detect")


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Detection:
    """Upload an image file, validate dimensions/format, run detection, and save results.

    - Validates MIME type, file size (streaming 413 cutoff), and Pillow image decoding.
    - Saves image to disk under a generated UUID filename in UPLOAD_DIR/images/.
    - Returns 503 if detector is not loaded/available.
    - Runs inference via run_inference() protecting against queue saturation (503) and timeout (504).
    - Cleans up orphan uploaded image file if inference or database commit fails.
    - Persists detection metadata, counts, and bounding box JSON in the database.
    """
    detector = getattr(request.app.state, "detector", None)
    if detector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Detector not available",
        )

    # 1. Validate, decode to RGB, and persist upload to disk
    rgb_image, file_path = validate_and_save_image(file, settings=settings)

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

        # 3. Store Detection record in database
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

    # 4. Evaluate alerts (non-blocking for image detection failure)
    try:
        from app.services.alert_service import evaluate_detection
        evaluate_detection(db, detection_record)
    except Exception as exc:
        logger.error(f"Alert evaluation failed for detection {detection_record.id}: {exc}", exc_info=True)

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
