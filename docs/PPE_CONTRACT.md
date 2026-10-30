# PPE Compliance Detection Contract (ppe.v1)

This specification defines the strict contract between computer-vision detectors (such as YOLO or synthetic test harnesses) and the backend rules engine.

---

## 1. Purpose & Separation of Concerns

The central architectural principle of this system is strict separation of detection from policy:

- **What the Detector Computes**: Pure visual observation. The detector identifies persons, observes whether equipment is present, missing, or uncertain on each person, identifies isolated equipment, reads visible badge markers, and notes visibility conditions. The detector **never** checks site policies or compliance rules.
- **What the Backend Computes**: Policy evaluation. The rules engine inspects the tenant's required equipment list, computes compliance verdicts per worker, calculates site-wide summaries, compiles human-readable audit explanations, and stores the results.

A model developer integrating a new YOLO detector needs only to output valid visual observations conforming to schema `ppe.v1`.

---

## 2. Three Inviolable Rules

Every detector and evaluator implementation must uphold three foundational rules:

1. **Worker Isolation**: Equipment assigned to one worker belongs strictly to that worker. A spare helmet or a co-worker's vest can never satisfy another worker's requirement.
2. **Unassigned Items Discarded**: Equipment detected in the environment but not worn on the appropriate body region (e.g. a helmet resting on a bench or held in hand) must be reported as `unassigned_items`. Unassigned items are completely ignored when determining worker compliance.
3. **No Guessing Under Occlusion**: If a worker's head or torso cannot be clearly observed due to camera angle, obstruction, distance, or lighting, the detector must set status to `uncertain` with appropriate flags (e.g. `partly_occluded`). The system never penalizes workers with an unverified violation when visibility is insufficient.

---

## 3. Full JSON Example (Three Workers)

The following payload represents the final stored `PpeExtra` structure containing three workers:

```json
{
  "schema": "ppe.v1",
  "camera_name": "Gate-3-North",
  "required_equipment": ["helmet", "vest"],
  "workers": [
    {
      "id": 1,
      "bbox": [100, 150, 300, 650],
      "person_confidence": 0.94,
      "helmet": {
        "status": "present",
        "confidence": 0.92,
        "bbox": [140, 155, 260, 250]
      },
      "vest": {
        "status": "present",
        "confidence": 0.89,
        "bbox": [120, 260, 280, 480]
      },
      "badge_id": 14,
      "flags": [],
      "notes": ["Worker fully visible and facing camera."],
      "verdict": "compliant",
      "missing": [],
      "uncertain_items": [],
      "why": [
        "Worker fully visible and facing camera.",
        "Helmet: detected on the worker's head (confidence 0.92).",
        "Vest: detected on the worker's torso (confidence 0.89).",
        "Required equipment: helmet, vest."
      ],
      "worker_id": null,
      "worker_name": null,
      "identified": false
    },
    {
      "id": 2,
      "bbox": [350, 160, 520, 640],
      "person_confidence": 0.91,
      "helmet": {
        "status": "missing",
        "confidence": 0.88,
        "bbox": null
      },
      "vest": {
        "status": "present",
        "confidence": 0.95,
        "bbox": [365, 270, 505, 490]
      },
      "badge_id": null,
      "flags": ["helmet_in_hand"],
      "notes": ["Worker is carrying hard hat in left hand."],
      "verdict": "violation",
      "missing": ["helmet"],
      "uncertain_items": [],
      "why": [
        "Worker is carrying hard hat in left hand.",
        "Helmet: not found on this worker.",
        "Vest: detected on the worker's torso (confidence 0.95).",
        "Required equipment: helmet, vest."
      ],
      "worker_id": null,
      "worker_name": null,
      "identified": false
    },
    {
      "id": 3,
      "bbox": [550, 200, 720, 680],
      "person_confidence": 0.85,
      "helmet": {
        "status": "present",
        "confidence": 0.87,
        "bbox": [580, 205, 690, 300]
      },
      "vest": {
        "status": "uncertain",
        "confidence": null,
        "bbox": null
      },
      "badge_id": null,
      "flags": ["partly_occluded"],
      "notes": ["Torso occluded by wooden pallet stack."],
      "verdict": "uncertain",
      "missing": [],
      "uncertain_items": ["vest"],
      "why": [
        "Torso occluded by wooden pallet stack.",
        "Helmet: detected on the worker's head (confidence 0.87).",
        "Vest: torso not clearly visible, needs a human check.",
        "Required equipment: helmet, vest."
      ],
      "worker_id": null,
      "worker_name": null,
      "identified": false
    }
  ],
  "unassigned_items": [
    {
      "label": "helmet",
      "confidence": 0.86,
      "bbox": [480, 420, 530, 470],
      "reason": "helmet is not on a head"
    }
  ],
  "pipeline": {
    "low_light_enhanced": false,
    "zoom_pass_workers": []
  },
  "summary": {
    "workers": 3,
    "compliant": 1,
    "violations": 1,
    "uncertain": 1,
    "missing_helmet": 1,
    "missing_vest": 0,
    "compliance_rate": 0.333,
    "violating_worker_ids": [2],
    "required_equipment": ["helmet", "vest"]
  }
}
```

---

## 4. Field Reference Table

### Detector Output (`PpeExtraRaw`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `schema` | string | Must be exactly `"ppe.v1"`. |
| `workers` | list[`PpeWorkerRaw`] | List of detected workers, ordered left to right. |
| `unassigned_items` | list[`UnassignedItem`] | Detections not assigned to any worker. |
| `pipeline` | `PpePipelineInfo` | Preprocessing and multi-pass pipeline flags. |

### Worker Raw (`PpeWorkerRaw`)
| Field | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | int | >= 1, unique | Sequential index ordered left-to-right by bbox x1. |
| `bbox` | list[int] | `[x1, y1, x2, y2]` | Bounding box of person in original image pixels. |
| `person_confidence` | float | 0.0 to 1.0 | Confidence of person detector. |
| `helmet` | `PpeItem` | Object | Status, confidence, and box of helmet on this worker. |
| `vest` | `PpeItem` | Object | Status, confidence, and box of safety vest on this worker. |
| `badge_id` | int or null | 0 to 49 or null | Optical badge/marker ID if detected inside torso box. |
| `flags` | list[str] | Allowed set | Diagnostic tags (see Allowed Flags). |
| `notes` | list[str] | Max 200 chars/note | Plain-text detector observations. No emojis. |

### Final Worker Fields (`PpeWorker`)
Computed by the backend rules engine:
| Field | Type | Description |
| :--- | :--- | :--- |
| `verdict` | string | `"compliant"`, `"violation"`, or `"uncertain"`. |
| `missing` | list[str] | Subset of required equipment determined missing. |
| `uncertain_items`| list[str] | Subset of required equipment determined uncertain. |
| `why` | list[str] | Audit trail sentences explaining the verdict. |
| `worker_id` | int or null | Registry worker database ID (null in BP1). |
| `worker_name` | str or null | Registry worker full name (null in BP1). |
| `identified` | bool | True if mapped to worker registry (false in BP1). |

### Item Observation (`PpeItem`)
| Field | Type | Constraints |
| :--- | :--- | :--- |
| `status` | string | `"present"`, `"missing"`, or `"uncertain"`. |
| `confidence` | float or null | 0.0 to 1.0 for present/missing; must be null for uncertain. |
| `bbox` | list[int] or null | Coordinates when present; must be null for missing/uncertain. |

### Allowed Flags
- `helmet_in_hand`: Worker is holding a helmet rather than wearing it on the head.
- `helmet_not_on_head`: Helmet is positioned improperly (e.g. hung on belt or tool).
- `hi_vis_not_vest`: High-visibility clothing observed, but does not meet safety vest standards.
- `partly_occluded`: Worker body, head, or torso obstructed by objects or edges.
- `low_light`: Scene or worker region exhibits severe underexposure.
- `small_or_distant`: Worker resolution is too low for reliable feature extraction.

---

## 5. Verdict Rules and Precedence

For each worker, compliance is evaluated strictly against the configured `required_equipment` list:

1. **Violation Precedence**: If **any** required equipment item has status `"missing"`, the worker verdict is `"violation"`.
2. **Uncertain Precedence**: If no required item is missing, but **any** required equipment item has status `"uncertain"`, the worker verdict is `"uncertain"`.
3. **Compliant Precedence**: If **all** required equipment items have status `"present"`, the worker verdict is `"compliant"`.

Items detected on a worker that are **not** present in `required_equipment` are retained in the report but have zero effect on the compliance verdict.

---

## 6. Edge Cases & Reporting Standards

### A. Helmet Held in Hand
- Worker `helmet.status`: `"missing"`
- Worker `helmet.bbox`: `null`
- Worker `flags`: includes `"helmet_in_hand"`
- Worker `notes`: e.g. `"Worker is holding helmet in hand."`
- `unassigned_items`: Add entry with `label: "helmet"`, its coordinates in the hand, and `reason: "helmet is not on a head"`.

### B. High-Visibility Shirt or Jacket (Non-Vest)
- Worker `vest.status`: `"missing"`
- Worker `vest.bbox`: `null`
- Worker `flags`: includes `"hi_vis_not_vest"`
- Worker `notes`: e.g. `"High-visibility shirt detected, but safety vest is missing."`

### C. Occlusion / Low Resolution
- If head is obscured: `helmet.status = "uncertain"`, `confidence = null`, `bbox = null`, flag `"partly_occluded"`.
- If torso is obscured: `vest.status = "uncertain"`, `confidence = null`, `bbox = null`, flag `"partly_occluded"`.
- Do not mark an obscured item as `"missing"`.

---

## 7. Coordinate Space & Geometry

- All bounding boxes are specified in original image pixels: `[x1, y1, x2, y2]`.
- Coordinates must satisfy `0 <= x1 < x2 <= width` and `0 <= y1 < y2 <= height` (1 pixel boundary tolerance is allowed during validation).
- Coordinates must never be normalized to 0.0-1.0 floats; they must be integer pixels.

---

## 8. Suggestions for YOLO Partner Implementation

These suggestions provide practical starting heuristics for the real YOLO detector team:

1. **Head Region Assignment**: Define the worker head band as the upper 20% to 25% of the person box ($y_1$ to $y_1 + 0.25 \times h$). Check if a detected helmet bounding box overlaps with this band with an Intersection-over-Union (IoU) or vertical containment $\ge 0.4$.
2. **Torso Region Assignment**: Define the worker torso band as the middle 25% to 65% of the person box ($y_1 + 0.25 \times h$ to $y_1 + 0.65 \times h$). Check if a detected safety vest bounding box overlaps with this band.
3. **Left-to-Right Ordering**: Sort all person detections by $x_1$ coordinate ascending before assigning sequential IDs `1, 2, ...`.
4. **Validation Test Harness**: Use `app.services.ppe_rules.validate_detector_output` in your detector unit tests to verify that every output payload adheres strictly to schema constraints.
