# Computer Vision Microservice Integration Contract

Version: 1.0  
Status: Active  
Audience: Computer Vision Microservice Engineer & Backend Integration Engineer  

---

## 1. Purpose & System Boundaries

This document defines the formal integration contract between the **Backend Core Service** and the dedicated **Computer Vision (CV) Microservice**.

### Separation of Responsibilities

- **CV Microservice (Owned by CV Engineer)**:
  - Executes video decoding, frame sampling, and deep learning inference (YOLO, ByteTrack/DeepSORT, OCR).
  - Maintains spatio-temporal worker tracking across frames (`track_id`).
  - Evaluates equipment presence (helmet, safety vest) over multi-frame confirmation windows.
  - Generates compliance verdicts (`compliant`, `violation`, `uncertain`) and extracts worker identity evidence.
  - Persists artifacts (annotated frames, violation snapshots, video clips).
  - Dispatches real-time event envelopes to the backend via HTTP webhooks.
  - **Crucial Rule**: The CV microservice decides compliance verdicts for this flow; the backend does not recalculate them.

- **Backend Core Service (Owned by Backend Engineer)**:
  - Manages tenant accounts, permissions, user authentication, and rate limiting.
  - Accepts user uploads and camera registrations, creating persistent `Job` entities.
  - Submits media and processing parameters to the CV microservice.
  - Ingests, validates, deduplicates, and stores asynchronous CV events.
  - Dispatches WebSocket notifications and alerts to connected frontend dashboards.
  - Serves historical queries, aggregated analytics, and reports.

- **Frontend Application**:
  - Interacts exclusively with the Backend Core Service.
  - **Rule**: The frontend **never** connects directly to the CV microservice. All commands and data flow through the backend.

```
+--------------------+        HTTP / WS         +----------------------+        Internal HTTP        +----------------------+
|                    | -----------------------> |                      | --------------------------> |                      |
|  React Dashboard   |                          |  Backend Core (API)  |                             |   CV Microservice    |
|     (Frontend)     | <----------------------- |      (FastAPI)       | <-------------------------- |    (YOLO / OCR)      |
+--------------------+      Events & Alerts     +----------------------+       Webhook Events        +----------------------+
```

---

## 2. Common Architectural Rules

1. **Timestamps**:
   - Every timestamp must strictly adhere to ISO 8601 UTC with a trailing `Z` designator (for example, `2026-10-31T12:00:00Z`).
   - Local timezone offsets and naive timestamps without timezone information are rejected by the backend with HTTP 422.

2. **Event Identity & UUIDs**:
   - Every event envelope must have a globally unique `event_id` formatted as a UUID v4 string (e.g., `550e8400-e29b-41d4-a716-446655440000`).

3. **Contract Versioning**:
   - `contract_version` must be `"1.0"` in all request bodies, response payloads, and event envelopes.
   - The backend validates major version compatibility (`1.x`). Any payload specifying an unsupported major version (such as `"2.0"`) is rejected with HTTP 422.

4. **Service-to-Service Authentication**:
   - Internal communication is secured via the `X-Service-Key` HTTP header.
   - Two distinct cryptographically random keys (32+ characters) are used:
     - `CV_SERVICE_API_KEY`: Outbound from Backend to CV Microservice.
     - `CV_EVENTS_API_KEY`: Inbound from CV Microservice to Backend (`POST /internal/api/v1/cv/events`).
   - Missing or mismatched keys return HTTP 401 with `{ "detail": "Invalid service credentials" }`.

5. **Delivery Guarantees & Retries**:
   - Webhook delivery from the CV microservice to the backend is **at-least-once**.
   - If the backend returns a non-2xx status code or a network timeout occurs, the CV microservice must retry sending the **exact same `event_id`** using exponential backoff with jitter.
   - The CV microservice must process events asynchronously in background worker queues and must **never** block video processing if the backend response is delayed.

6. **Ordering & Idempotency**:
   - Network transmission does not guarantee in-order delivery. Every event carries a monotonic, per-job integer `sequence` number.
   - The backend enforces strict idempotency on `event_id`. Duplicate deliveries are acknowledged with HTTP 200 and `{ "status": "duplicate" }` without executing handlers twice.

---

## 3. CV Service Endpoints (Implemented by CV Engineer)

The backend interacts with the CV microservice through the following REST API endpoints:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness and readiness probe for the CV microservice. |
| `POST` | `/api/v1/jobs` | Submit new media for processing (`multipart/form-data`). |
| `GET` | `/api/v1/jobs/{job_id}` | Query execution status and progress of an active or finished job. |
| `GET` | `/api/v1/jobs/{job_id}/result` | Retrieve full consolidated detection report upon completion. |
| `GET` | `/api/v1/jobs/{job_id}/artifacts`| List generated visual artifacts (bounding box snapshots, clips). |

### Proposed Additions (To Be Confirmed by CV Engineer)
The backend proposes the following additions to finalize production workflows:
1. `GET /api/v1/artifacts/{artifact_id}`: Dedicated endpoint to stream and download binary artifacts (JPEG snapshots, MP4 violation clips). Must support HTTP Range requests (`bytes=...`) to enable video scrubbing in browser players.
2. `POST /api/v1/jobs/{job_id}/cancel`: Gracefully terminates background analysis of a queued or running job, freeing GPU resources.
3. Artifact Type `"live_frame"`: For continuous RTSP camera streams, the CV service periodically writes an annotated latest frame snapshot labeled `"live_frame"` that the backend polls approximately once per second for preview cards.

---

## 4. Job Submission & Lifecycle Schemas

### A. Job Submission Request (`POST /api/v1/jobs`)
Submitted by backend as `multipart/form-data`:
- `metadata`: JSON string conforming to the Job Metadata schema.
- `file` (optional): Binary video/image file (present for file uploads, omitted for RTSP streams).

#### Job Metadata JSON Schema
```json
{
  "contract_version": "1.0",
  "external_job_id": "9f1c7d24-6019-4b2e-a581-cb782b137c41:1",
  "source": {
    "type": "video",
    "url": null
  },
  "camera": {
    "name": "Gate-3-North"
  },
  "required_equipment": ["helmet", "vest"],
  "options": {
    "frame_skip": 5,
    "confirm_frames": 3
  },
  "events_url": "http://127.0.0.1:8000/internal/api/v1/cv/events"
}
```

#### Job Creation Response (HTTP 202 Accepted)
```json
{
  "contract_version": "1.0",
  "job_id": "cv-job-8842af19",
  "external_job_id": "9f1c7d24-6019-4b2e-a581-cb782b137c41:1",
  "status": "queued",
  "created_at": "2026-10-31T12:00:00Z"
}
```

### B. Job Status (`GET /api/v1/jobs/{job_id}`)
```json
{
  "job_id": "cv-job-8842af19",
  "external_job_id": "9f1c7d24-6019-4b2e-a581-cb782b137c41:1",
  "status": "running",
  "progress": 65,
  "created_at": "2026-10-31T12:00:00Z",
  "started_at": "2026-10-31T12:00:02Z",
  "finished_at": null,
  "error": null
}
```

---

## 5. Final Consolidated Result Schema (`GET /api/v1/jobs/{job_id}/result`)

```json
{
  "contract_version": "1.0",
  "job_id": "cv-job-8842af19",
  "external_job_id": "9f1c7d24-6019-4b2e-a581-cb782b137c41:1",
  "source_type": "video",
  "camera_name": "Gate-3-North",
  "required_equipment": ["helmet", "vest"],
  "media": {
    "duration_s": 124.5,
    "fps": 25.0,
    "width": 1920,
    "height": 1080,
    "frames_total": 3112,
    "frames_processed": 622
  },
  "summary": {
    "workers_tracked": 14,
    "compliant": 10,
    "violations": 3,
    "uncertain": 1,
    "unidentified_workers": 2,
    "violation_events": 4,
    "compliance_rate": 0.714
  },
  "workers": [
    {
      "track_id": 101,
      "first_seen_s": 2.4,
      "last_seen_s": 48.2,
      "final_verdict": "compliant",
      "items": {
        "helmet": { "status": "present", "confidence": 0.94 },
        "vest": { "status": "present", "confidence": 0.91 }
      },
      "identity": {
        "method": "ocr",
        "code": "EMP-4091",
        "confidence": 0.88,
        "verified": true
      },
      "flags": [],
      "why": [
        "Worker observed wearing helmet and safety vest across all frames.",
        "Badge OCR read EMP-4091 on torso."
      ]
    },
    {
      "track_id": 102,
      "first_seen_s": 14.1,
      "last_seen_s": 35.8,
      "final_verdict": "violation",
      "items": {
        "helmet": { "status": "missing", "confidence": 0.92 },
        "vest": { "status": "present", "confidence": 0.89 }
      },
      "identity": null,
      "flags": ["helmet_in_hand"],
      "why": [
        "Helmet was held in right hand rather than worn on head.",
        "Safety vest confirmed present."
      ]
    }
  ],
  "violations": [
    {
      "violation_key": "cv-job-8842af19:trk-102:v1",
      "track_id": 102,
      "missing_items": ["helmet"],
      "started_at": "2026-10-31T12:00:16Z",
      "started_s": 14.1,
      "ended_at": "2026-10-31T12:00:37Z",
      "duration_s": 21.7,
      "confidence": 0.92,
      "identity": null,
      "snapshot_artifact_id": "art-snap-102-001",
      "why": ["Missing helmet confirmed across consecutive sampled frames."]
    }
  ],
  "timeline": [
    { "t_s": 0.0, "workers": 1, "violations": 0 },
    { "t_s": 15.0, "workers": 3, "violations": 1 },
    { "t_s": 30.0, "workers": 2, "violations": 1 }
  ],
  "pipeline": {
    "model": "yolov8x-ppe-v2.1",
    "tracker": "bytetrack",
    "ocr": true
  }
}
```

---

## 6. Real-Time Webhook Events (`POST /internal/api/v1/cv/events`)

The CV microservice pushes event envelopes to the backend as processing unfolds.

### Event Envelope Specification
A request body may contain a single event envelope object or a batch:
```json
{
  "contract_version": "1.0",
  "events": [
    {
      "contract_version": "1.0",
      "event_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "type": "job.progress",
      "occurred_at": "2026-10-31T12:00:10Z",
      "job_id": "cv-job-8842af19",
      "external_job_id": "9f1c7d24-6019-4b2e-a581-cb782b137c41:1",
      "sequence": 1,
      "data": {
        "progress": 25,
        "frames_processed": 150
      }
    }
  ]
}
```

### Event Types Reference

#### 1. `job.progress`
Periodic processing progress update:
```json
{
  "type": "job.progress",
  "data": {
    "progress": 45,
    "frames_processed": 280
  }
}
```

#### 2. `job.completed`
Job finished successfully:
```json
{
  "type": "job.completed",
  "data": {
    "summary": {
      "workers_tracked": 12,
      "compliant": 10,
      "violations": 2,
      "uncertain": 0,
      "unidentified_workers": 1,
      "violation_events": 2,
      "compliance_rate": 0.833
    }
  }
}
```

#### 3. `job.failed`
Fatal job failure:
```json
{
  "type": "job.failed",
  "data": {
    "error": {
      "code": "CORRUPT_VIDEO_CONTAINER",
      "message": "MOOV atom missing or unreadable in video stream."
    }
  }
}
```

#### 4. `worker.status`
Emitted when a worker's verdict, equipment status, or identity **changes** (not every single frame):
```json
{
  "type": "worker.status",
  "data": {
    "track_id": 102,
    "verdict": "violation",
    "items": {
      "helmet": { "status": "missing", "confidence": 0.91 },
      "vest": { "status": "present", "confidence": 0.95 }
    },
    "identity": null,
    "flags": ["helmet_in_hand"],
    "why": ["Worker removed helmet while walking through entrance."],
    "bbox": {
      "x1": 320.0,
      "y1": 180.0,
      "x2": 490.0,
      "y2": 620.0
    },
    "frame_index": 210,
    "timestamp_s": 8.4
  }
}
```

#### 5. `violation.confirmed`
Emitted when an unequipped worker remains non-compliant across the confirmation threshold:
```json
{
  "type": "violation.confirmed",
  "data": {
    "violation_key": "cv-job-8842af19:trk-102:v1",
    "track_id": 102,
    "missing_items": ["helmet"],
    "started_at": "2026-10-31T12:00:16Z",
    "started_s": 14.1,
    "ended_at": null,
    "duration_s": null,
    "confidence": 0.92,
    "identity": null,
    "snapshot_artifact_id": "art-snap-102-001",
    "why": ["Worker missing helmet across 3 consecutive sample frames."]
  }
}
```

#### 6. `violation.ended`
Emitted when an ongoing violation episode concludes (worker wears equipment or leaves FOV):
```json
{
  "type": "violation.ended",
  "data": {
    "violation_key": "cv-job-8842af19:trk-102:v1",
    "ended_at": "2026-10-31T12:00:37Z",
    "duration_s": 21.0
  }
}
```

#### 7. `camera.status`
RTSP streaming health telemetry:
```json
{
  "type": "camera.status",
  "data": {
    "state": "connected",
    "message": "RTSP stream established at 1920x1080 30fps."
  }
}
```

---

## 7. Backend Intake Response Specification

The backend evaluates event batches and returns HTTP 200 with individual status codes:

```json
{
  "contract_version": "1.0",
  "results": [
    {
      "event_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "status": "accepted",
      "reason": null
    },
    {
      "event_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "duplicate",
      "reason": null
    },
    {
      "event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "status": "rejected",
      "reason": "data.missing_items: missing_items must not be empty."
    }
  ]
}
```

### Response Status Codes
- **HTTP 200 OK**: Envelope or batch received and parsed. Each event contains its individual outcome (`accepted`, `duplicate`, or `rejected`).
- **HTTP 401 Unauthorized**: Missing or invalid `X-Service-Key` header.
- **HTTP 413 Payload Too Large**: Request body exceeds `CV_EVENTS_MAX_BODY_KB` (512 KB).
- **HTTP 422 Unprocessable Entity**: Unparseable JSON, batch size exceeding `CV_EVENTS_MAX_BATCH` (100), or unsupported `contract_version` major version.

---

## 8. Semantic Rules Enforced by the Backend

The backend verifies semantic consistency to maintain data integrity across the platform:

1. **Non-Empty Missing Items**: Any `violation.confirmed` event must have a non-empty `missing_items` array containing unique items from `["helmet", "vest"]`.
2. **Uncertain Verdict Isolation**: A verdict of `"uncertain"` must **never** be reported as a violation. If a worker's head or torso is occluded or in low light, status must remain `"uncertain"`.
3. **Violation Key Stability**: `violation_key` is unique and deterministic for each continuous violation episode for that worker in that job (e.g. `{job_id}:trk-{track_id}:v{index}`). Repeated events with the same key reference the same violation episode.
4. **Tracking ID Distinction**: `track_id` is an internal tracker identifier for spatial association within a video. It is **never** an employee ID.
5. **Verified Identity Standard**: A worker is considered identified **only** when `method` is non-null (`ocr` or `marker`), `code` is a non-empty string, and `verified` is strictly `true`. The CV service must never guess or fabricate worker identities.

---

## 9. Implementation Checklist for CV Engineer

- [ ] Implement `GET /health` responding with service readiness and GPU memory stats.
- [ ] Implement `POST /api/v1/jobs` supporting multipart form metadata and file uploads.
- [ ] Implement `external_job_id` deduplication on job creation.
- [ ] Configure webhook dispatching with `X-Service-Key` set to `CV_EVENTS_API_KEY`.
- [ ] Implement exponential backoff and retries on webhook network errors.
- [ ] Ensure webhook dispatching is decoupled from processing loops via background queues.
- [ ] Enforce ISO 8601 UTC timestamps with trailing `Z`.
- [ ] Filter out duplicate worker status events; emit `worker.status` only when state changes.
- [ ] Confirm and provide feedback on the three proposed additions below.

---

## 10. Open Questions for the CV Engineer

Please confirm the following three proposed extensions during sprint alignment:
1. **Artifact Download Endpoint**: Does `GET /api/v1/artifacts/{artifact_id}` with HTTP 206 Partial Content (Range requests) fit your storage architecture (local disk vs MinIO/S3 pre-signed URLs)?
2. **Job Cancellation**: Does `POST /api/v1/jobs/{job_id}/cancel` support clean thread/subprocess termination without leaking GPU VRAM?
3. **RTSP Live Frame Feed**: Can your streaming pipeline maintain a fresh JPEG snapshot of the latest annotated frame under artifact type `"live_frame"` for continuous camera monitoring?
