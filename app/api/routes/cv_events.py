"""Internal endpoint for ingesting asynchronous CV microservice event envelopes."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_cv_events_key
from app.core.config import Settings, get_settings
from app.core.context import get_request_id
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.cv_event import CvEvent
from app.models.job import Job
from app.schemas.cv import CvEventEnvelope, CvEventsResponse
from app.services.cv_events import dispatch_event

router = APIRouter(prefix="/internal/api/v1/cv", tags=["CV Events"])
logger = get_logger("vision_api.cv_events")
envelope_adapter = TypeAdapter(CvEventEnvelope)


@router.post(
    "/events",
    response_model=CvEventsResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest CV microservice event envelopes",
    include_in_schema=False,
)
@limiter.exempt
async def ingest_cv_events(
    request: Request,
    key: str = Depends(require_cv_events_key),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Any:
    """Secure event intake for the external CV microservice.

    - Authenticated via X-Service-Key matching CV_EVENTS_API_KEY.
    - Exempt from public IP rate limiting.
    - Enforces body size limit CV_EVENTS_MAX_BODY_KB (HTTP 413).
    - Accepts single envelope or batch up to CV_EVENTS_MAX_BATCH (HTTP 422 if exceeded).
    - Rejects unsupported contract major versions with HTTP 422.
    - Idempotent: duplicate event_id returns 'duplicate' without error or duplicate handler calls.
    - Validates individual events: invalid events return 'rejected' with reason without failing batch.
    - Dispatches registered handlers for accepted events.
    """
    # 1. Enforce body size limit
    raw_body = await request.body()
    max_bytes = settings.CV_EVENTS_MAX_BODY_KB * 1024
    if len(raw_body) > max_bytes:
        req_id = get_request_id() or str(uuid.uuid4())
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "detail": f"Request body exceeds maximum allowed limit of {settings.CV_EVENTS_MAX_BODY_KB} KB",
                "request_id": req_id,
            },
            headers={"X-Request-ID": req_id},
        )

    # 2. Parse JSON body
    if not raw_body:
        raise RequestValidationError(
            [
                {
                    "type": "missing_body",
                    "loc": ("body",),
                    "msg": "Request body cannot be empty.",
                    "input": None,
                }
            ]
        )

    try:
        body_json = json.loads(raw_body)
    except Exception as exc:
        raise RequestValidationError(
            [
                {
                    "type": "json_invalid",
                    "loc": ("body",),
                    "msg": f"Malformed JSON body: {exc}",
                    "input": None,
                }
            ]
        )

    # 3. Validate contract_version if provided at the top level
    if isinstance(body_json, dict) and "contract_version" in body_json:
        ver = str(body_json["contract_version"]).strip()
        parts = ver.split(".")
        if not parts or parts[0] != "1":
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("body", "contract_version"),
                        "msg": f"Unsupported contract_version '{ver}'. Expected major version 1.",
                        "input": ver,
                    }
                ]
            )

    # 4. Extract envelopes list (single object vs batch)
    raw_events: List[Any]
    if isinstance(body_json, dict) and "events" in body_json:
        events_val = body_json["events"]
        if not isinstance(events_val, list):
            raise RequestValidationError(
                [
                    {
                        "type": "list_type",
                        "loc": ("body", "events"),
                        "msg": "Input should be a valid list of events.",
                        "input": events_val,
                    }
                ]
            )
        raw_events = events_val
    elif isinstance(body_json, dict):
        raw_events = [body_json]
    elif isinstance(body_json, list):
        raw_events = body_json
    else:
        raise RequestValidationError(
            [
                {
                    "type": "model_type",
                    "loc": ("body",),
                    "msg": "Expected a JSON object envelope or batch object with 'events'.",
                    "input": body_json,
                }
            ]
        )

    # Check batch limit
    if len(raw_events) > settings.CV_EVENTS_MAX_BATCH:
        raise RequestValidationError(
            [
                {
                    "type": "too_many_events",
                    "loc": ("body", "events"),
                    "msg": f"Batch size {len(raw_events)} exceeds maximum allowed of {settings.CV_EVENTS_MAX_BATCH}.",
                    "input": len(raw_events),
                }
            ]
        )

    # 5. Process each event independently
    results: List[Dict[str, Any]] = []

    for raw_event in raw_events:
        # Extract event_id if present for response tracking
        raw_event_id: str
        if isinstance(raw_event, dict) and "event_id" in raw_event and raw_event["event_id"]:
            raw_event_id = str(raw_event["event_id"])
        else:
            raw_event_id = str(uuid.uuid4())

        # Check for event-level unsupported contract major version
        if isinstance(raw_event, dict) and "contract_version" in raw_event:
            ev_ver = str(raw_event["contract_version"]).strip()
            ev_parts = ev_ver.split(".")
            if not ev_parts or ev_parts[0] != "1":
                results.append(
                    {
                        "event_id": raw_event_id,
                        "status": "rejected",
                        "reason": f"Unsupported contract_version '{ev_ver}'. Expected major version 1.",
                    }
                )
                continue

        # A. Validate schema
        try:
            if not isinstance(raw_event, dict):
                raise ValueError("Event must be a JSON object.")
            validated_event = envelope_adapter.validate_python(raw_event)
        except (ValidationError, ValueError, TypeError) as val_err:
            short_reason = str(val_err)
            if hasattr(val_err, "errors"):
                # Clean error formatting for CV engineer
                err_msgs = [f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg', '')}" for e in val_err.errors()[:2]]
                short_reason = "; ".join(err_msgs)
            logger.warning(
                f"Rejected invalid CV event '{raw_event_id}': {short_reason}"
            )
            results.append(
                {
                    "event_id": raw_event_id,
                    "status": "rejected",
                    "reason": short_reason[:200],
                }
            )
            continue

        # B. Idempotency: Attempt database insertion with savepoint
        savepoint = db.begin_nested()
        is_duplicate = False
        try:
            cv_event_row = CvEvent(
                event_id=validated_event.event_id,
                job_id=None,
                cv_job_id=validated_event.job_id,
                type=validated_event.type,
                occurred_at=validated_event.occurred_at,
                received_at=datetime.now(timezone.utc),
                sequence=validated_event.sequence,
                payload=raw_event,
                outcome="accepted",
                error=None,
            )

            # Map matching Job entity by cv_job_id
            job = db.query(Job).filter(Job.cv_job_id == validated_event.job_id).first()
            if job is not None:
                cv_event_row.job_id = job.id
            else:
                logger.warning(
                    f"CV event '{validated_event.event_id}' references unknown cv_job_id '{validated_event.job_id}'"
                )

            db.add(cv_event_row)
            savepoint.commit()
            db.commit()
        except IntegrityError:
            savepoint.rollback()
            is_duplicate = True

        if is_duplicate:
            results.append(
                {
                    "event_id": validated_event.event_id,
                    "status": "duplicate",
                    "reason": None,
                }
            )
            continue

        # C. Dispatch registered event handlers
        handler_sp = db.begin_nested()
        try:
            dispatch_event(db, validated_event, job)
            handler_sp.commit()
            db.commit()
            results.append(
                {
                    "event_id": validated_event.event_id,
                    "status": "accepted",
                    "reason": None,
                }
            )
        except Exception as handler_exc:
            logger.exception(
                f"Handler execution failed for event '{validated_event.event_id}': {handler_exc}"
            )
            handler_sp.rollback()
            # Mark the event row outcome as handler_failed
            try:
                db.query(CvEvent).filter(CvEvent.event_id == validated_event.event_id).update(
                    {
                        "outcome": "handler_failed",
                        "error": str(handler_exc)[:200],
                    }
                )
                db.commit()
            except Exception:
                db.rollback()

            # Still respond 'accepted' so the CV service does not resend endlessly
            results.append(
                {
                    "event_id": validated_event.event_id,
                    "status": "accepted",
                    "reason": None,
                }
            )

    return {
        "contract_version": "1.0",
        "results": results,
    }
