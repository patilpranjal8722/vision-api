# Vision API - Frontend Developer API Reference

This document provides a comprehensive, reality-tested API reference for frontend developers integrating with the `vision-api` backend.

All endpoints, headers, error structures, rate limits, and WebSocket protocols described here match the exact implementation in the codebase.

---

## Table of Contents

1. [Base URL & Interactive Documentation](#base-url--interactive-documentation)
2. [Standard Error Shape & Request Tracking](#standard-error-shape--request-tracking)
3. [Authentication & Authorization Flow](#authentication--authorization-flow)
4. [Pagination & Filtering Conventions](#pagination--filtering-conventions)
5. [Rate Limits & Throttling](#rate-limits--throttling)
6. [Complete REST API Reference Table](#complete-rest-api-reference-table)
7. [Detailed REST Endpoint Specifications](#detailed-rest-endpoint-specifications)
8. [Real-Time WebSocket Protocol](#real-time-websocket-protocol)
9. [Copy-Paste JavaScript Client Example](#copy-paste-javascript-client-example)

---

## Base URL & Interactive Documentation

- **Base URL (Local)**: `http://127.0.0.1:8000`
- **Base URL (Docker)**: `http://localhost:8000`
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI 3.1 JSON Schema**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json) (or file [docs/openapi.json](openapi.json))

---

## Standard Error Shape & Request Tracking

Every error response returned by the backend (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 503, 504) strictly follows a uniform JSON structure:

```json
{
  "detail": "Error description or validation errors",
  "request_id": "0df62f27-6f81-4ba2-b2d2-28df3b782987"
}
```

### Key Error Guidelines
1. **`request_id` Correlation**:
   - Every response includes the `X-Request-ID` HTTP header matching `request_id` in the body.
   - If you send a custom `X-Request-ID` header (1–64 alphanumeric characters, underscores, or hyphens: `^[a-zA-Z0-9_-]{1,64}$`), the server preserves and echoes it. Otherwise, a UUID4 is generated.
   - Always display or log `request_id` when showing error dialogs to users so backend logs can be traced immediately.
2. **Validation Errors (`HTTP 422`)**:
   - `detail` contains an array of field errors:
     ```json
     {
       "detail": [
         {
           "type": "string_too_short",
           "loc": ["body", "password"],
           "msg": "String should have at least 8 characters"
         }
       ],
       "request_id": "..."
     }
     ```
   - For security, password values and tokens are automatically stripped from error payloads.
3. **Internal Server Errors (`HTTP 500`)**:
   - Returns generic `{"detail": "Internal server error", "request_id": "..."}`. Stack traces and database internals are never leaked to clients.

---

## Authentication & Authorization Flow

The API uses stateless **JWT (JSON Web Tokens)** with HMAC-SHA256 signing.

```
[ Frontend Client ]                                      [ Backend API ]
         |                                                      |
         | --- 1. POST /auth/register (Create account) ---------> |
         | <--- 201 Created (UserOut) -------------------------- |
         |                                                      |
         | --- 2. POST /auth/login (OAuth2 form-data) ----------> |
         | <--- 200 OK (access_token + refresh_token) ---------- |
         |                                                      |
         | --- 3. Authenticated Request with Bearer Token ------> |
         |        Header: "Authorization: Bearer <access_token>" |
         | <--- 200 OK (Protected Data) ------------------------ |
         |                                                      |
         | --- 4. When Access Token Expires (401) -------------> |
         | --- 5. POST /auth/refresh {refresh_token} -----------> |
         | <--- 200 OK (New access_token + refresh_token) ------ |
```

### 1. Registration (`POST /auth/register`)
- Content-Type: `application/json`
- Default role is strictly enforced as `"user"`.
- Password complexity requirements:
  - Minimum **8 characters**, maximum **128 characters**.
  - At least **1 uppercase letter** (`A-Z`).
  - At least **1 lowercase letter** (`a-z`).
  - At least **1 digit** (`0-9`).
  - At least **1 special character** (e.g. `!@#$%^&*()_+-=[]{}|;:,.<>?`).

### 2. Login (`POST /auth/login`)
- Content-Type: `application/x-www-form-urlencoded`
- Fields:
  - `username`: Email address **or** username (both supported).
  - `password`: Plaintext password.
- Response:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```

### 3. Sending the Token
Send the access token in the standard HTTP `Authorization` header on all protected endpoints:
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 4. Refreshing the Token (`POST /auth/refresh`)
- Content-Type: `application/json`
- Body: `{"refresh_token": "eyJhbGci..."}`
- Returns a new token pair (`access_token` and rotated `refresh_token`).

---

## Pagination & Filtering Conventions

List endpoints (`GET /detect/history`, `GET /jobs`, `GET /alerts`) adhere to consistent pagination parameters:

| Parameter | Type | Default | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `page` | integer | `1` | `ge=1` | 1-indexed page number. |
| `limit` | integer | `20` | `ge=1`, `le=100` | Number of items per page (maximum 100). |

- **Sorting**: Records are always sorted in descending chronological order (**newest first**).
- **Data Scoping**: Standard users only see records they created. Users with role `"admin"` can view all records across the system.

---

## Rate Limits & Throttling

When a rate limit is exceeded, the server returns `HTTP 429 Too Many Requests` with:
- Standard error JSON: `{"detail": "Rate limit exceeded: ...", "request_id": "..."}`
- Response header: `Retry-After: 60` (cooldown duration in seconds)

Configured defaults:
- **General Endpoints**: `120 requests/minute`
- **Login (`POST /auth/login`)**: `5 requests/minute`
- **Registration (`POST /auth/register`)**: `10 requests/minute`
- **Token Refresh (`POST /auth/refresh`)**: `10 requests/minute`
- **File Uploads (`POST /detect/image`, `POST /detect/video`)**: `20 requests/minute`
- **Concurrent Active Jobs Limit**: Maximum `3` pending/running video jobs per user.
- **WebSocket Connections Limit**: Maximum `3` active WebSocket connections per user.

---

## Complete REST API Reference Table

| Method | Path | Auth Required | Minimum Role | Request Body / Parameters | Success Status | Possible Errors |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | No | None | None | `200 OK` | `500` |
| `GET` | `/ready` | No | None | None | `200 OK` | `503` |
| `POST` | `/auth/register` | No | None | JSON: `{email, username, password}` | `201 Created` | `400, 409, 422, 429` |
| `POST` | `/auth/login` | No | None | Form: `username`, `password` | `200 OK` | `401, 422, 429` |
| `POST` | `/auth/refresh` | No | None | JSON: `{refresh_token}` | `200 OK` | `401, 422, 429` |
| `GET` | `/users/me` | **Yes** | `user` | None | `200 OK` | `401, 429` |
| `GET` | `/users/` | **Yes** | `admin` | None | `200 OK` | `401, 403, 429` |
| `POST` | `/detect/image` | **Yes** | `user` | `multipart/form-data`: `file`, `required_equipment`, `camera_name` | `201 Created` | `400, 401, 413, 415, 422, 429, 500, 503, 504` |
| `POST` | `/detect/video` | **Yes** | `user` | `multipart/form-data`: `file`, query: `frame_skip` | `202 Accepted` | `400, 401, 413, 415, 429, 503` |
| `GET` | `/detect/config` | **Yes** | `user` | None | `200 OK` | `401, 429` |
| `GET` | `/detect/history` | **Yes** | `user` | Query: `page`, `limit` | `200 OK` | `401, 422, 429` |
| `GET` | `/detect/{detection_id}` | **Yes** | `user` | Path: `detection_id` | `200 OK` | `401, 404, 429` |
| `GET` | `/detect/{detection_id}/image` | **Yes** | `user` | Path: `detection_id` | `200 OK` | `401, 404, 429` |
| `GET` | `/jobs/{job_id}` | **Yes** | `user` | Path: `job_id` | `200 OK` | `401, 404, 429` |
| `GET` | `/jobs` | **Yes** | `user` | Query: `page`, `limit`, `status` | `200 OK` | `401, 422, 429` |
| `GET` | `/alerts` | **Yes** | `user` | Query: `page`, `limit`, `level`, `is_read` | `200 OK` | `401, 422, 429` |
| `GET` | `/alerts/unread-count` | **Yes** | `user` | None | `200 OK` | `401, 429` |
| `PATCH` | `/alerts/{alert_id}/read` | **Yes** | `user` | Path: `alert_id` | `200 OK` | `401, 404, 429` |
| `POST` | `/alerts/read-all` | **Yes** | `user` | None | `200 OK` | `401, 429` |
| `GET` | `/analytics/summary` | **Yes** | `user` | Query: `date_from`, `date_to` | `200 OK` | `401, 422, 429` |
| `GET` | `/analytics/timeseries` | **Yes** | `user` | Query: `interval`, `date_from`, `date_to` | `200 OK` | `401, 422, 429` |

---

## Detailed REST Endpoint Specifications

### 1. Health & Readiness

#### `GET /health`
Liveness check returning service status, model readiness, database connectivity, and active connections.
```json
{
  "status": "ok",
  "app_name": "vision-api",
  "version": "1.0.0",
  "timestamp": "2026-10-26T14:15:00.000000+00:00",
  "detector": "dummy",
  "model_loaded": true,
  "detector_is_placeholder": true,
  "database": "ok",
  "active_jobs": 0,
  "ws_connections": 1
}
```

#### `GET /ready`
Readiness probe for container orchestrators.
- **200 OK**: `{"status": "ready"}`
- **503 Service Unavailable**: `{"detail": "Service not ready: detector check failed", "request_id": "..."}`

---

### 2. Detection Endpoints

#### `POST /detect/image`
Synchronously upload an image (JPEG, PNG, WebP up to 10 MB) for object and PPE detection.
- **Request**: `multipart/form-data` with fields:
  - `file` (Binary File, required): Image file.
  - `required_equipment` (string, optional): Comma-separated subset of required equipment (`helmet`, `vest`). Defaults to server setting `DEFAULT_REQUIRED_EQUIPMENT` (`helmet,vest`). Invalid values return `422 Unprocessable Entity` with location `["body", "required_equipment"]`.
  - `camera_name` (string, optional): Camera or checkpoint label up to 60 characters (`[a-zA-Z0-9 _.-]`). Empty strings are converted to `null`. Invalid characters or excessive length return `422 Unprocessable Entity` with location `["body", "camera_name"]`.
- **Response (`201 Created`)** with PPE detector (`DETECTOR_BACKEND=ppe_dummy` or YOLO):
```json
{
  "id": 14,
  "user_id": 2,
  "source_type": "image",
  "file_path": "uploads/images/3f82cb5a-6058-45dc-913a-a131b790c370.jpg",
  "detector_name": "ppe-dummy",
  "total_count": 2,
  "results": {
    "objects": [
      {
        "label": "person",
        "confidence": 0.94,
        "bbox": {"x1": 50, "y1": 40, "x2": 250, "y2": 440}
      },
      {
        "label": "helmet",
        "confidence": 0.92,
        "bbox": {"x1": 90, "y1": 45, "x2": 210, "y2": 130}
      },
      {
        "label": "vest",
        "confidence": 0.89,
        "bbox": {"x1": 70, "y1": 140, "x2": 230, "y2": 300}
      }
    ],
    "total_count": 2,
    "image_width": 640,
    "image_height": 480,
    "inference_ms": 14.2,
    "detector_name": "ppe-dummy",
    "extra": {
      "schema": "ppe.v1",
      "camera_name": "Gate-1",
      "required_equipment": ["helmet", "vest"],
      "workers": [
        {
          "id": 1,
          "bbox": [50, 40, 250, 440],
          "person_confidence": 0.94,
          "helmet": {"status": "present", "confidence": 0.92, "bbox": [90, 45, 210, 130]},
          "vest": {"status": "present", "confidence": 0.89, "bbox": [70, 140, 230, 300]},
          "badge_id": 12,
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
        }
      ],
      "unassigned_items": [],
      "pipeline": {
        "low_light_enhanced": false,
        "zoom_pass_workers": []
      },
      "summary": {
        "workers": 1,
        "compliant": 1,
        "violations": 0,
        "uncertain": 0,
        "missing_helmet": 0,
        "missing_vest": 0,
        "compliance_rate": 1.0,
        "violating_worker_ids": [],
        "required_equipment": ["helmet", "vest"]
      }
    }
  },
  "created_at": "2026-10-26T14:20:00+00:00"
}
```

#### `GET /detect/config`
Retrieve detection backend configuration, PPE schema metadata, and file upload parameters for clients.
- **Auth**: Bearer token required (`user` or `admin`).
- **Response (`200 OK`)**:
```json
{
  "detector": {
    "name": "ppe-dummy",
    "is_placeholder": true,
    "loaded": true
  },
  "ppe": {
    "schema": "ppe.v1",
    "supported_equipment": ["helmet", "vest"],
    "default_required_equipment": ["helmet", "vest"]
  },
  "upload": {
    "max_image_mb": 10,
    "allowed_image_types": ["image/jpeg", "image/png", "image/webp"],
    "max_image_dimension": 6000,
    "max_video_mb": 100,
    "allowed_video_types": ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"]
  },
  "confidence_threshold": 0.5
}
```

#### `GET /detect/{detection_id}/image`
Retrieve the original uploaded image file for an image detection.
- **Auth**: Bearer token required. Accessible by the resource owner or an `admin`.
- **Response (`200 OK`)**: Binary image stream.
  - Header `Content-Type`: MIME type matching the original image (e.g. `image/jpeg`).
  - Header `Cache-Control`: `private, max-age=300`.
- **Errors**:
  - `401 Unauthorized`: Missing or invalid Bearer token.
  - `404 Not Found`: Detection does not exist, belongs to another user, source is not `"image"`, the image file is missing from disk, or stored path escapes upload directory.


#### `POST /detect/video`
Upload a video file (MP4, MOV, AVI, WebM up to 100 MB) for asynchronous processing.
- **Query Parameter**: `frame_skip` (optional integer between 1 and 60, defaults to server configuration `FRAME_SKIP=5`).
- **Response (`202 Accepted`)**:
```json
{
  "job_id": "8a0c4f86-90b5-4b07-99b4-b203c94f5df3",
  "status": "pending",
  "progress": 0,
  "created_at": "2026-10-26T14:25:00+00:00"
}
```

---

### 3. Background Jobs

#### `GET /jobs/{job_id}`
Inspect status and progress of an asynchronous job.
```json
{
  "id": "8a0c4f86-90b5-4b07-99b4-b203c94f5df3",
  "user_id": 2,
  "type": "video",
  "status": "done",
  "progress": 100,
  "input_path": "uploads/videos/8a0c4f86-90b5-4b07-99b4-b203c94f5df3.mp4",
  "result": {
    "summary": {
      "total_frames_processed": 120,
      "total_objects_detected": 45,
      "max_objects_in_single_frame": 4,
      "frames_failed": 0
    },
    "timeline": [
      {
        "frame_index": 0,
        "timestamp": 0.0,
        "total_count": 2,
        "objects": [{"label": "person", "confidence": 0.85, "bbox": {"x1": 10, "y1": 20, "x2": 80, "y2": 150}}]
      }
    ],
    "peak_frame": {
      "frame_index": 35,
      "timestamp": 1.4,
      "total_count": 4,
      "objects": []
    }
  },
  "error": null,
  "created_at": "2026-10-26T14:25:00+00:00",
  "updated_at": "2026-10-26T14:25:12+00:00"
}
```
*Note: The `result` field is `null` until `status` transitions to `"done"`.*

---

### 4. Alerts & Analytics

#### `GET /alerts`
List notifications triggered by detection thresholds (`warning` >= 10 objects, `critical` >= 20 objects).
- Query params: `page`, `limit`, `level` (`warning` | `critical`), `is_read` (`true` | `false`).

#### `GET /analytics/summary`
Get aggregated statistics over a date range (`date_from`, `date_to` in ISO format).
```json
{
  "total_detections": 85,
  "total_objects": 230,
  "avg_count": 2.71,
  "max_count": 14,
  "counts_by_source": {
    "image": 50,
    "video": 25,
    "stream": 10
  },
  "alerts_by_level": {
    "warning": 4,
    "critical": 1
  },
  "top_labels": {
    "person": 160,
    "car": 50,
    "bicycle": 20
  },
  "truncated": false
}
```

---

## Real-Time WebSocket Protocol

The vision API provides two WebSocket channels:
1. `WS /ws/alerts`: Push feed for threshold alerts.
2. `WS /ws/stream`: Real-time streaming webcam/video frame analysis.

### Mandatory Connection & Authentication Handshake

For security against URL token exposure, tokens are **NOT passed in query parameters**. Instead, clients connect and must authenticate with an initial JSON payload within **5 seconds** (`WS_AUTH_TIMEOUT_SECONDS`):

```json
{
  "type": "auth",
  "token": "<YOUR_ACCESS_TOKEN>"
}
```

- **Authentication Success**: Server responds with:
  ```json
  {"type": "auth_ok"}
  ```
- **Authentication Failure**: Server closes the socket with code `4401` and reason (e.g. `"Authentication timeout"`, `"Invalid or expired token"`, `"User inactive or not found"`).
- **Connection Limit Exceeded**: Server closes with code `4429` (max 3 connections per user).
- **Forbidden Origin**: Server closes with code `4403`.

---

### Channel 1: Real-Time Alerts (`/ws/alerts`)

- **Server Alert Push**:
  ```json
  {
    "type": "alert",
    "alert": {
      "id": 12,
      "user_id": 2,
      "detection_id": 48,
      "level": "warning",
      "message": "Warning threshold exceeded: 12 objects detected",
      "is_read": false,
      "created_at": "2026-10-26T14:30:00+00:00"
    }
  }
  ```
- **Heartbeat (Keep-Alive)**:
  - Client sends: `{"type": "ping"}`
  - Server replies: `{"type": "pong"}`

---

### Channel 2: Live Video Stream (`/ws/stream`)

1. Complete the initial auth handshake (`auth` -> `auth_ok`).
2. Client sends **binary frames** (raw JPEG, PNG, or WebP bytes). Frame size must not exceed **2048 KB** (`WS_MAX_FRAME_KB`).
3. Flow Control: **Latest-Frame-Wins**.
   - If the client sends frames faster than model inference speed, the server buffers only the most recent frame and drops intermediary frames to eliminate lag.
4. **Server Detection Response**:
  ```json
  {
    "type": "detections",
    "frame_id": 105,
    "skipped_since_last": 2,
    "result": {
      "objects": [
        {
          "label": "person",
          "confidence": 0.912,
          "bbox": {
            "x1": 120.5,
            "y1": 80.0,
            "x2": 260.0,
            "y2": 390.0
          }
        }
      ],
      "total_count": 1,
      "image_width": 640,
      "image_height": 480,
      "inference_ms": 11.2,
      "detector_name": "dummy",
      "extra": {}
    }
  }
  ```
5. **Server Error Messages**:
  ```json
  {
    "type": "error",
    "message": "Undecodable or invalid image frame bytes"
  }
  ```

---

## Copy-Paste JavaScript Client Example

Here is a complete, production-ready ES6 / Browser JavaScript client demonstrating authentication, REST requests, and WebSocket streaming:

```javascript
/**
 * VisionApiClient - Complete Frontend Integration Helper
 */
class VisionApiClient {
  constructor(baseUrl = "http://127.0.0.1:8000") {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.wsBaseUrl = this.baseUrl.replace(/^http/, "ws");
    this.accessToken = localStorage.getItem("access_token") || null;
    this.refreshToken = localStorage.getItem("refresh_token") || null;
  }

  // Helper for REST requests with automatic Bearer token injection
  async fetchWithAuth(path, options = {}) {
    const headers = options.headers ? new Headers(options.headers) : new Headers();
    if (this.accessToken) {
      headers.set("Authorization", `Bearer ${this.accessToken}`);
    }

    const response = await fetch(`${this.baseUrl}${path}`, { ...options, headers });

    // Handle token expiration: attempt automatic refresh once
    if (response.status === 401 && this.refreshToken && path !== "/auth/refresh" && path !== "/auth/login") {
      const refreshed = await this.refreshTokens();
      if (refreshed) {
        headers.set("Authorization", `Bearer ${this.accessToken}`);
        return fetch(`${this.baseUrl}${path}`, { ...options, headers });
      }
    }

    return response;
  }

  // 1. Authenticate with username or email
  async login(usernameOrEmail, password) {
    const form = new URLSearchParams();
    form.append("username", usernameOrEmail);
    form.append("password", password);

    const res = await fetch(`${this.baseUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Login failed");
    }

    const data = await res.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    localStorage.setItem("access_token", this.accessToken);
    localStorage.setItem("refresh_token", this.refreshToken);
    return data;
  }

  // 2. Refresh Token pair
  async refreshTokens() {
    try {
      const res = await fetch(`${this.baseUrl}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      });

      if (!res.ok) throw new Error("Refresh expired");
      const data = await res.json();
      this.accessToken = data.access_token;
      this.refreshToken = data.refresh_token;
      localStorage.setItem("access_token", this.accessToken);
      localStorage.setItem("refresh_token", this.refreshToken);
      return true;
    } catch {
      this.logout();
      return false;
    }
  }

  logout() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  // 3. Upload an Image for Object Detection
  async detectImage(fileBlob) {
    const formData = new FormData();
    formData.append("file", fileBlob, "upload.jpg");

    const res = await this.fetchWithAuth("/detect/image", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Detection failed: ${res.status}`);
    }
    return res.json();
  }

  // 4. Connect to Real-time Alerts WebSocket Feed
  connectAlertsFeed(onAlertReceived) {
    if (!this.accessToken) throw new Error("Login required before opening WebSocket");

    const ws = new WebSocket(`${this.wsBaseUrl}/ws/alerts`);

    ws.onopen = () => {
      // Step 1: Send authentication message immediately upon open
      ws.send(JSON.stringify({ type: "auth", token: this.accessToken }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "auth_ok") {
        console.log("WebSocket Alerts channel authenticated!");
      } else if (msg.type === "alert") {
        onAlertReceived(msg.alert);
      }
    };

    ws.onclose = (e) => {
      console.warn("Alerts socket closed:", e.code, e.reason);
    };

    return ws;
  }

  // 5. Connect to Live Video Stream WebSocket Feed
  connectStream(onDetectionResult) {
    if (!this.accessToken) throw new Error("Login required before opening WebSocket");

    const ws = new WebSocket(`${this.wsBaseUrl}/ws/stream`);
    ws.binaryType = "blob";

    ws.onopen = () => {
      // Step 1: Authenticate
      ws.send(JSON.stringify({ type: "auth", token: this.accessToken }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "auth_ok") {
        console.log("Stream WebSocket channel authenticated and ready for frames!");
      } else if (msg.type === "detections") {
        onDetectionResult(msg.result, msg.frame_id, msg.skipped_since_last);
      } else if (msg.type === "error") {
        console.error("Stream inference error:", msg.message);
      }
    };

    return {
      socket: ws,
      // Helper to send frame blob from an HTML5 <canvas>
      sendCanvasFrame: (canvasElement) => {
        if (ws.readyState === WebSocket.OPEN) {
          canvasElement.toBlob(
            (blob) => {
              if (blob) ws.send(blob);
            },
            "image/jpeg",
            0.75
          );
        }
      },
    };
  }
}

// Example Usage:
// const client = new VisionApiClient("http://127.0.0.1:8000");
// await client.login("admin@example.com", "Str0ng!Pass");
// const alertFeed = client.connectAlertsFeed((alert) => console.log("New alert:", alert));
```
