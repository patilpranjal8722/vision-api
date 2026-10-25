"""Background job runner and video inference processing worker."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional
from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.detection import Detection
from app.models.job import Job
from app.services.video.factory import get_frame_reader

logger = get_logger("vision_api.job_runner")


def process_video_job(
    job_id: str,
    app: FastAPI,
    settings: Settings,
    frame_skip: int = 5,
) -> None:
    """Execute video inference pipeline in a dedicated worker thread.

    Worker Contract:
    1. Instantiates a dedicated database session with SessionLocal(); guarantees db.close().
    2. Updates status to 'running' and records progress.
    3. Opens frame reader and executes detector on sampled frames.
    4. Tracks frames, counts, timeline, and peak frame.
    5. Saves progress in small increments to prevent SQLite locks.
    6. Persists summary JSON in Job.result and creates a corresponding Detection record.
    7. Catches all exceptions, logging traceback internally while storing a sanitized
       short error message in Job.error (never stack traces or file paths).
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Worker could not find job {job_id}")
            return

        # Mark job as running
        job.status = "running"
        job.progress = 0
        job.updated_at = now
        db.commit()

        detector = getattr(app.state, "detector", None)
        if detector is None:
            raise RuntimeError("Detector not available on app.state")

        reader = get_frame_reader(settings)
        with reader.open(job.input_path) as video_capture:
            total_frames = video_capture.total_frames
            fps = video_capture.fps

            frames_processed = 0
            counts: List[int] = []
            timeline: List[Dict[str, Any]] = []
            peak_count = 0
            peak_frame: Optional[Dict[str, Any]] = None

            last_progress_time = datetime.now(timezone.utc).timestamp()
            last_reported_progress = 0

            for frame_idx, timestamp_s, pil_image in video_capture.iter_frames(frame_skip=frame_skip):
                detection_res = detector.detect(pil_image)
                count = detection_res.total_count

                frames_processed += 1
                counts.append(count)
                timeline.append({
                    "frame_index": frame_idx,
                    "timestamp_s": timestamp_s,
                    "total_count": count,
                })

                if peak_frame is None or count > peak_count:
                    peak_count = count
                    peak_frame = {
                        "frame_index": frame_idx,
                        "timestamp_s": timestamp_s,
                        "total_count": count,
                        "objects": [obj.model_dump() for obj in detection_res.objects],
                    }

                # Update progress based on frame_index vs total_frames
                current_progress = min(
                    99,
                    max(1, int(((frame_idx + 1) / max(1, total_frames)) * 100)),
                )
                current_time = datetime.now(timezone.utc).timestamp()

                # Update DB at most once per second or every 5% step
                if (current_time - last_progress_time >= 1.0) or (
                    current_progress >= last_reported_progress + 5
                ):
                    job.progress = current_progress
                    job.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    last_progress_time = current_time
                    last_reported_progress = current_progress

            # Downsample timeline to at most 500 points
            if len(timeline) > 500:
                step = len(timeline) / 500.0
                downsampled_timeline = [timeline[int(i * step)] for i in range(500)]
                timeline = downsampled_timeline

            duration_s = round(total_frames / fps, 2) if fps > 0 else 0.0
            avg_count = round(sum(counts) / max(1, len(counts)), 2) if counts else 0.0
            max_count = max(counts) if counts else 0

            result_data = {
                "summary": {
                    "frames_total": total_frames,
                    "frames_processed": frames_processed,
                    "frame_skip": frame_skip,
                    "fps": fps,
                    "duration_seconds": duration_s,
                    "max_count": max_count,
                    "avg_count": avg_count,
                    "detector_name": detector.name,
                },
                "timeline": timeline,
                "peak_frame": peak_frame or {
                    "frame_index": 0,
                    "timestamp_s": 0.0,
                    "total_count": 0,
                    "objects": [],
                },
            }

            # Finalize Job record
            job.progress = 100
            job.status = "done"
            job.result = result_data
            job.error = None
            job.updated_at = datetime.now(timezone.utc)

            # Create ONE Detection row for this video job
            detection_record = Detection(
                user_id=job.user_id,
                job_id=job.id,
                source_type="video",
                file_path=job.input_path,
                detector_name=detector.name,
                total_count=peak_count,
                results=result_data,
            )
            db.add(detection_record)
            db.commit()
            db.refresh(detection_record)

            # Evaluate alerts for the video detection (non-blocking)
            try:
                from app.services.alert_service import evaluate_detection
                evaluate_detection(db, detection_record)
            except Exception as alert_exc:
                logger.error(f"Alert evaluation failed for video job {job_id}: {alert_exc}", exc_info=True)

            logger.info(
                f"Job {job_id} completed successfully",
                extra={"job_id": job_id, "frames_processed": frames_processed, "peak_count": peak_count},
            )

    except Exception as exc:
        logger.exception(f"Execution error processing video job {job_id}: {exc}")
        try:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error = "Processing failed"
                job.updated_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as db_exc:
            logger.error(f"Failed to record job failure in database: {db_exc}", exc_info=True)
    finally:
        db.close()


class JobRunner:
    """Manages background task execution thread pool and job submissions."""

    def __init__(self, app: FastAPI, settings: Optional[Settings] = None) -> None:
        self.app = app
        self.settings = settings or get_settings()
        self.executor = ThreadPoolExecutor(
            max_workers=self.settings.MAX_CONCURRENT_JOBS,
            thread_name_prefix="job-runner-",
        )

    def submit(self, job_id: str, frame_skip: int = 5) -> None:
        """Submit job for execution either inline or in a worker thread."""
        if self.settings.JOB_RUNNER_INLINE:
            process_video_job(job_id, self.app, self.settings, frame_skip=frame_skip)
        else:
            self.executor.submit(
                process_video_job, job_id, self.app, self.settings, frame_skip
            )

    def shutdown(self, wait: bool = False) -> None:
        """Shutdown threadpool executor on application shutdown."""
        self.executor.shutdown(wait=wait)


def reconcile_stale_jobs() -> int:
    """Find jobs left in 'pending' or 'running' status and mark them failed."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        stale_jobs = (
            db.query(Job)
            .filter(Job.status.in_(["pending", "running"]))
            .all()
        )
        count = len(stale_jobs)
        for job in stale_jobs:
            job.status = "failed"
            job.error = "Server restarted while the job was running"
            job.updated_at = now
        if count > 0:
            db.commit()
            logger.warning(
                f"Reconciled {count} stale jobs from prior session",
                extra={"reconciled_count": count},
            )
        return count
    finally:
        db.close()
