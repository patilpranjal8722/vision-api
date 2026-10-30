"""CV microservice event handler registry and built-in dispatch logic.

Provides hook registration for incoming CV events and maintains Job entity state.
"""

from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.job import Job

logger = get_logger("vision_api.cv_events")

EventHandler = Callable[[Session, Any, Optional[Job]], None]
_handlers: Dict[str, List[EventHandler]] = {}


def register_event_handler(event_type: str, handler: EventHandler) -> None:
    """Register a handler callback for a specific CV event type."""
    _handlers.setdefault(event_type, []).append(handler)


def clear_event_handlers() -> None:
    """Clear all registered handlers and re-initialize defaults (useful for testing)."""
    _handlers.clear()
    _register_builtin_handlers()


def dispatch_event(db: Session, event: Any, job: Optional[Job]) -> None:
    """Execute all handlers registered for the event's type."""
    handlers = _handlers.get(event.type, [])
    for handler in handlers:
        handler(db, event, job)


# ---------------------------------------------------------------------------
# Built-in Event Handlers
# ---------------------------------------------------------------------------

def _handle_job_progress(db: Session, event: Any, job: Optional[Job]) -> None:
    """Update job progress and transition status from pending to running."""
    if job is None:
        return

    # Events for terminal jobs are stored but never mutate job state
    if job.status in ("done", "failed"):
        logger.info(
            f"Ignoring job.progress for job '{job.id}' in terminal state '{job.status}'"
        )
        return

    if job.status == "pending":
        job.status = "running"

    job.cv_status = "running"

    # Progress must be strictly monotonically non-decreasing
    new_progress = int(event.data.progress)
    if new_progress > job.progress:
        job.progress = new_progress


def _handle_job_completed(db: Session, event: Any, job: Optional[Job]) -> None:
    """Mark job as done with progress 100 and record completion timestamp."""
    if job is None:
        return

    if job.status in ("done", "failed"):
        logger.info(
            f"Ignoring job.completed for job '{job.id}' in terminal state '{job.status}'"
        )
        return

    job.status = "done"
    job.cv_status = "completed"
    job.progress = 100
    job.finished_at = event.occurred_at

    # Record summary in job result
    if hasattr(event.data, "summary"):
        summary_dict = event.data.summary.model_dump()
        if job.result and isinstance(job.result, dict):
            job.result["summary"] = summary_dict
        else:
            job.result = {"summary": summary_dict}


def _handle_job_failed(db: Session, event: Any, job: Optional[Job]) -> None:
    """Mark job as failed with sanitized error message."""
    if job is None:
        return

    if job.status in ("done", "failed"):
        logger.info(
            f"Ignoring job.failed for job '{job.id}' in terminal state '{job.status}'"
        )
        return

    job.status = "failed"
    job.cv_status = "failed"
    job.finished_at = event.occurred_at

    # Sanitize and truncate error to at most 200 characters
    err_code = getattr(event.data.error, "code", "UNKNOWN")
    err_msg = getattr(event.data.error, "message", "Processing failed")
    sanitized = f"[{err_code}] {err_msg}"[:200]
    job.error = sanitized


def _register_builtin_handlers() -> None:
    """Register built-in event handlers for core job lifecycle events."""
    register_event_handler("job.progress", _handle_job_progress)
    register_event_handler("job.completed", _handle_job_completed)
    register_event_handler("job.failed", _handle_job_failed)


# Register defaults upon module import
_register_builtin_handlers()
