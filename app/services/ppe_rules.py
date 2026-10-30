"""PPE compliance rules engine.

Pure evaluation functions with no database or HTTP dependencies.
Decides worker compliance, parses equipment parameters, and validates detector output.
"""

from typing import Any, Dict, List, Optional
from app.schemas.detection import DetectionResult
from app.schemas.ppe import (
    ALLOWED_FLAGS,
    ORDERED_EQUIPMENT,
    PpeExtra,
    PpeItem,
    PpePipelineInfo,
    PpeSummary,
    PpeWorker,
    PpeWorkerRaw,
    UnassignedItem,
)


class InvalidDetectorOutput(ValueError):
    """Raised when detector output fails structural, bounds, or semantic validation."""


def parse_required_equipment(value: Optional[str] = None, default: Optional[str] = None) -> List[str]:
    """Parse, sanitize, validate, and order required equipment list.

    Args:
        value: Comma-separated equipment string (e.g. "helmet,vest").
        default: Fallback equipment string if value is None or empty.

    Returns:
        List[str]: Canonical ordered list of required equipment ('helmet', 'vest').

    Raises:
        ValueError: If the equipment list is empty or contains unrecognized items.
    """
    raw = value if value is not None else default

    if raw is None or not raw.strip():
        raise ValueError("Required equipment cannot be empty. Valid options are: helmet, vest.")

    tokens = [t.strip().lower() for t in raw.split(",") if t.strip()]
    if not tokens:
        raise ValueError("Required equipment cannot be empty. Valid options are: helmet, vest.")

    items_set = set(tokens)
    for item in items_set:
        if item not in ORDERED_EQUIPMENT:
            raise ValueError(
                f"Invalid required equipment: '{item}'. Valid options are: {', '.join(ORDERED_EQUIPMENT)}."
            )

    # Return in strict canonical order: helmet then vest
    return [eq for eq in ORDERED_EQUIPMENT if eq in items_set]


def validate_detector_output(result: DetectionResult, image_width: int, image_height: int) -> None:
    """Validate that detector output conforms to the PPE v1 contract.

    Args:
        result: DetectionResult containing raw PPE extra payload.
        image_width: Width of the analyzed image in pixels.
        image_height: Height of the analyzed image in pixels.

    Raises:
        InvalidDetectorOutput: If any contract requirement is violated.
    """
    if not isinstance(result.extra, dict):
        raise InvalidDetectorOutput("DetectionResult.extra must be a dictionary.")

    schema = result.extra.get("schema")
    if schema != "ppe.v1":
        raise InvalidDetectorOutput(f"Invalid schema: expected 'ppe.v1', got {schema!r}.")

    raw_workers = result.extra.get("workers")
    if not isinstance(raw_workers, list):
        raise InvalidDetectorOutput("Field 'workers' in extra must be a list.")

    tolerance = 1.0
    seen_ids = set()

    for idx, w in enumerate(raw_workers):
        if not isinstance(w, (dict, PpeWorkerRaw)):
            raise InvalidDetectorOutput(f"Worker at index {idx} must be a dict or PpeWorkerRaw.")

        w_dict = w if isinstance(w, dict) else w.model_dump()

        w_id = w_dict.get("id")
        if not isinstance(w_id, int) or w_id < 1:
            raise InvalidDetectorOutput(f"Worker at index {idx} has invalid id {w_id!r} (must be int >= 1).")

        if w_id in seen_ids:
            raise InvalidDetectorOutput(f"Duplicate worker id found: {w_id}.")
        seen_ids.add(w_id)

        # Validate person bounding box
        p_bbox = w_dict.get("bbox")
        if not isinstance(p_bbox, dict):
            raise InvalidDetectorOutput(f"Worker {w_id} has invalid bbox format.")

        px1, py1, px2, py2 = p_bbox.get("x1"), p_bbox.get("y1"), p_bbox.get("x2"), p_bbox.get("y2")
        if None in (px1, py1, px2, py2):
            raise InvalidDetectorOutput(f"Worker {w_id} bbox has missing coordinates.")

        if px1 >= px2 or py1 >= py2:
            raise InvalidDetectorOutput(f"Worker {w_id} has inverted coordinates: ({px1}, {py1}, {px2}, {py2}).")

        if (
            px1 < -tolerance
            or px2 > image_width + tolerance
            or py1 < -tolerance
            or py2 > image_height + tolerance
        ):
            raise InvalidDetectorOutput(
                f"Worker {w_id} bbox [{px1}, {py1}, {px2}, {py2}] exceeds image boundaries [{image_width}, {image_height}]."
            )

        # Person confidence
        p_conf = w_dict.get("person_confidence")
        if not isinstance(p_conf, (int, float)) or not (0.0 <= float(p_conf) <= 1.0):
            raise InvalidDetectorOutput(f"Worker {w_id} has person_confidence out of range: {p_conf!r}.")

        # Badge ID
        badge_id = w_dict.get("badge_id")
        if badge_id is not None:
            if not isinstance(badge_id, int) or not (0 <= badge_id <= 49):
                raise InvalidDetectorOutput(f"Worker {w_id} badge_id {badge_id!r} out of range (0 to 49).")

        # Flags
        flags = w_dict.get("flags", [])
        if not isinstance(flags, list):
            raise InvalidDetectorOutput(f"Worker {w_id} flags must be a list.")
        for flag in flags:
            if flag not in ALLOWED_FLAGS:
                raise InvalidDetectorOutput(f"Worker {w_id} has unrecognized flag: {flag!r}.")

        # Notes
        notes = w_dict.get("notes", [])
        if not isinstance(notes, list):
            raise InvalidDetectorOutput(f"Worker {w_id} notes must be a list.")
        for note in notes:
            if not isinstance(note, str) or len(note) > 200:
                raise InvalidDetectorOutput(f"Worker {w_id} has note exceeding 200 characters.")

        # Equipment items (helmet and vest)
        for item_key in ("helmet", "vest"):
            item_data = w_dict.get(item_key)
            if not isinstance(item_data, dict):
                raise InvalidDetectorOutput(f"Worker {w_id} missing equipment field '{item_key}'.")

            status = item_data.get("status")
            if status not in ("present", "missing", "uncertain"):
                raise InvalidDetectorOutput(f"Worker {w_id} item '{item_key}' has invalid status: {status!r}.")

            conf = item_data.get("confidence")
            bbox = item_data.get("bbox")

            if status == "present":
                if conf is None or not (0.0 <= float(conf) <= 1.0):
                    raise InvalidDetectorOutput(
                        f"Worker {w_id} present item '{item_key}' must have confidence between 0.0 and 1.0."
                    )
                if not isinstance(bbox, dict):
                    raise InvalidDetectorOutput(f"Worker {w_id} present item '{item_key}' must have bbox.")
                ix1, iy1, ix2, iy2 = bbox.get("x1"), bbox.get("y1"), bbox.get("x2"), bbox.get("y2")
                if None in (ix1, iy1, ix2, iy2) or ix1 >= ix2 or iy1 >= iy2:
                    raise InvalidDetectorOutput(f"Worker {w_id} item '{item_key}' has invalid bbox.")
                if (
                    ix1 < -tolerance
                    or ix2 > image_width + tolerance
                    or iy1 < -tolerance
                    or iy2 > image_height + tolerance
                ):
                    raise InvalidDetectorOutput(f"Worker {w_id} item '{item_key}' bbox exceeds image boundaries.")
            elif status == "missing":
                if conf is not None and not (0.0 <= float(conf) <= 1.0):
                    raise InvalidDetectorOutput(
                        f"Worker {w_id} missing item '{item_key}' confidence out of range: {conf!r}."
                    )
            elif status == "uncertain":
                if conf is not None:
                    raise InvalidDetectorOutput(
                        f"Worker {w_id} uncertain item '{item_key}' must have null confidence, got {conf!r}."
                    )
                if bbox is not None:
                    raise InvalidDetectorOutput(
                        f"Worker {w_id} uncertain item '{item_key}' must have null bbox, got {bbox!r}."
                    )

    # Validate unassigned items
    raw_unassigned = result.extra.get("unassigned_items", [])
    if not isinstance(raw_unassigned, list):
        raise InvalidDetectorOutput("Field 'unassigned_items' in extra must be a list.")

    for idx, u in enumerate(raw_unassigned):
        u_dict = u if isinstance(u, dict) else u.model_dump()
        label = u_dict.get("label")
        if label not in ORDERED_EQUIPMENT:
            raise InvalidDetectorOutput(f"Unassigned item at index {idx} has invalid label: {label!r}.")

        conf = u_dict.get("confidence")
        if conf is None or not (0.0 <= float(conf) <= 1.0):
            raise InvalidDetectorOutput(f"Unassigned item at index {idx} confidence out of range: {conf!r}.")

        u_bbox = u_dict.get("bbox")
        if not isinstance(u_bbox, dict):
            raise InvalidDetectorOutput(f"Unassigned item at index {idx} has invalid bbox.")

        ux1, uy1, ux2, uy2 = u_bbox.get("x1"), u_bbox.get("y1"), u_bbox.get("x2"), u_bbox.get("y2")
        if None in (ux1, uy1, ux2, uy2) or ux1 >= ux2 or uy1 >= uy2:
            raise InvalidDetectorOutput(f"Unassigned item at index {idx} has invalid bbox coordinates.")

        if (
            ux1 < -tolerance
            or ux2 > image_width + tolerance
            or uy1 < -tolerance
            or uy2 > image_height + tolerance
        ):
            raise InvalidDetectorOutput(
                f"Unassigned item at index {idx} bbox exceeds image boundaries."
            )


def evaluate_worker(raw: PpeWorkerRaw | Dict[str, Any], required: List[str]) -> PpeWorker:
    """Apply compliance rules to evaluate a single worker's PPE status.

    Verdict uses ONLY this worker's assigned items.
    Precedence:
      1. Any REQUIRED item with status 'missing' -> 'violation'
      2. Otherwise, any REQUIRED item with status 'uncertain' -> 'uncertain'
      3. Otherwise -> 'compliant'

    Args:
        raw: PpeWorkerRaw instance or raw worker dictionary.
        required: List of required equipment items (e.g. ['helmet', 'vest']).

    Returns:
        PpeWorker: Evaluated worker with verdict, missing items, uncertain items, and why sentences.
    """
    if isinstance(raw, dict):
        raw_worker = PpeWorkerRaw.model_validate(raw)
    else:
        raw_worker = raw

    missing: List[str] = []
    uncertain_items: List[str] = []

    # Check each required equipment item
    for eq in ORDERED_EQUIPMENT:
        if eq in required:
            item_status = getattr(raw_worker, eq).status
            if item_status == "missing":
                missing.append(eq)
            elif item_status == "uncertain":
                uncertain_items.append(eq)

    # Determine verdict based on precedence
    if missing:
        verdict = "violation"
    elif uncertain_items:
        verdict = "uncertain"
    else:
        verdict = "compliant"

    # Construct explanatory 'why' sentences
    why: List[str] = list(raw_worker.notes)

    for eq in required:
        item: PpeItem = getattr(raw_worker, eq)
        eq_capitalized = eq.capitalize()

        if item.status == "present":
            conf_str = f" (confidence {item.confidence:.2f})" if item.confidence is not None else ""
            location = "head" if eq == "helmet" else "torso"
            why.append(f"{eq_capitalized}: detected on the worker's {location}{conf_str}.")
        elif item.status == "missing":
            why.append(f"{eq_capitalized}: not found on this worker.")
        elif item.status == "uncertain":
            area = "head" if eq == "helmet" else "torso"
            why.append(f"{eq_capitalized}: {area} not clearly visible, needs a human check.")

    why.append(f"Required equipment: {', '.join(required)}.")

    return PpeWorker(
        id=raw_worker.id,
        bbox=raw_worker.bbox,
        person_confidence=raw_worker.person_confidence,
        helmet=raw_worker.helmet,
        vest=raw_worker.vest,
        badge_id=raw_worker.badge_id,
        flags=raw_worker.flags,
        notes=raw_worker.notes,
        verdict=verdict,
        missing=missing,
        uncertain_items=uncertain_items,
        why=why,
        worker_id=None,
        worker_name=None,
        identified=False,
    )


def build_summary(workers: List[PpeWorker], required: List[str]) -> PpeSummary:
    """Aggregate individual worker verdicts into a compliance summary.

    Args:
        workers: Evaluated PpeWorker list.
        required: Canonical list of required equipment items.

    Returns:
        PpeSummary: Aggregated compliance statistics.
    """
    total = len(workers)
    compliant = sum(1 for w in workers if w.verdict == "compliant")
    violations = sum(1 for w in workers if w.verdict == "violation")
    uncertain = sum(1 for w in workers if w.verdict == "uncertain")

    missing_helmet = sum(1 for w in workers if "helmet" in required and "helmet" in w.missing)
    missing_vest = sum(1 for w in workers if "vest" in required and "vest" in w.missing)

    compliance_rate = round(compliant / total, 3) if total > 0 else None
    violating_worker_ids = [w.id for w in workers if w.verdict == "violation"]

    return PpeSummary(
        workers=total,
        compliant=compliant,
        violations=violations,
        uncertain=uncertain,
        missing_helmet=missing_helmet,
        missing_vest=missing_vest,
        compliance_rate=compliance_rate,
        violating_worker_ids=violating_worker_ids,
        required_equipment=required,
    )


def apply_rules(
    result: DetectionResult,
    required: List[str],
    camera_name: Optional[str] = None,
) -> DetectionResult:
    """Apply compliance rules to raw detection results.

    Evaluates each worker against the required equipment, aggregates summary metrics,
    and returns a new DetectionResult with PpeExtra attached.

    Args:
        result: Raw DetectionResult from detector.
        required: List of required equipment.
        camera_name: Optional camera location identifier.

    Returns:
        DetectionResult: Final DetectionResult with enriched PpeExtra.
    """
    raw_workers = result.extra.get("workers", [])
    raw_unassigned = result.extra.get("unassigned_items", [])
    raw_pipeline = result.extra.get("pipeline", {})

    evaluated_workers: List[PpeWorker] = [
        evaluate_worker(w, required) for w in raw_workers
    ]

    summary = build_summary(evaluated_workers, required)

    unassigned_items = [
        u if isinstance(u, UnassignedItem) else UnassignedItem.model_validate(u)
        for u in raw_unassigned
    ]

    pipeline = (
        raw_pipeline
        if isinstance(raw_pipeline, PpePipelineInfo)
        else PpePipelineInfo.model_validate(raw_pipeline)
    )

    final_extra = PpeExtra(
        schema="ppe.v1",
        workers=evaluated_workers,
        unassigned_items=unassigned_items,
        pipeline=pipeline,
        summary=summary,
        required_equipment=required,
        camera_name=camera_name,
    )

    return DetectionResult(
        objects=result.objects,
        total_count=len(evaluated_workers),
        image_width=result.image_width,
        image_height=result.image_height,
        inference_ms=result.inference_ms,
        detector_name=result.detector_name,
        extra=final_extra.model_dump(),
    )
