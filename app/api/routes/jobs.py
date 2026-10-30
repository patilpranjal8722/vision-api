"""Job status inspection and history retrieval endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobOut

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobOut,
    summary="Retrieve job status and result",
)
def get_job_by_id(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    """Retrieve processing job status, progress, errors, and inference results.

    - Accessible if the job belongs to the requesting user or if user is an admin.
    - Returns 404 if not found or unauthorized to prevent disclosing job existence.
    - Result payload is populated only when status is 'done'; otherwise null.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if current_user.role != "admin" and job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Expose result only when processing has completed successfully
    result_data = job.result if job.status == "done" else None

    return JobOut(
        id=job.id,
        user_id=job.user_id,
        type=job.type,
        status=job.status,
        progress=job.progress,
        input_path=job.input_path,
        result=result_data,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get(
    "",
    response_model=List[JobOut],
    summary="List background jobs with pagination and status filter",
)
def list_jobs(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    job_status: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter jobs by status ('pending', 'running', 'done', 'failed')",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[JobOut]:
    """Retrieve job records ordered newest first.

    - Standard users only see their own jobs.
    - Administrators can view all background jobs.
    - Supports optional filtering by job status.
    """
    query = db.query(Job)
    if current_user.role != "admin":
        query = query.filter(Job.user_id == current_user.id)

    if job_status:
        query = query.filter(Job.status == job_status.strip().lower())

    offset = (page - 1) * limit
    jobs = (
        query.order_by(Job.created_at.desc(), Job.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        JobOut(
            id=j.id,
            user_id=j.user_id,
            type=j.type,
            status=j.status,
            progress=j.progress,
            input_path=j.input_path,
            result=j.result if j.status == "done" else None,
            error=j.error,
            created_at=j.created_at,
            updated_at=j.updated_at,
        )
        for j in jobs
    ]
