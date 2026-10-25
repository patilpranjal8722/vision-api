# vision-api 🚀

A modular, production-ready, reusable FastAPI backend template designed specifically for computer-vision hackathons and rapid ML prototyping.

The template provides an end-to-end operational backend (validation, storage, asynchronous task coordination, WebSocket feeds, and data persistence) with **zero heavy ML dependencies (no GPU, PyTorch, or OpenCV required during base development)**. A lightweight placeholder detector enables full frontend and infrastructure development until real model weights are plugged in.

---

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (High-performance async ASGI web framework)
- **ASGI Server**: [Uvicorn](https://www.uvicorn.org/) with `httptools` and `watchfiles`
- **Security & Cryptography**:
  - [PyJWT](https://pyjwt.readthedocs.io/) (Stateless HMAC-SHA256 access and refresh tokens)
  - [argon2-cffi](https://argon2-cffi.readthedocs.io/) (Modern password hashing using Argon2id)
- **Rate Limiting**: [slowapi](https://github.com/laurentS/slowapi) (IP-based endpoint request rate limiting)
- **Database & ORM**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (`DeclarativeBase`, `Mapped`, `mapped_column`)
- **Database Migrations**: [Alembic](https://alembic.sqlalchemy.org/) (with SQLite batch-mode support)
- **Configuration & Validation**: [Pydantic v2](https://docs.pydantic.dev/) (`EmailStr`), `email-validator`, and [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **File Uploads**: `python-multipart`
- **Testing**: [pytest](https://docs.pytest.org/) and [HTTPX](https://www.python-httpx.org/) (FastAPI `TestClient`)
- **Logging**: Structured JSON logging via standard library `logging`

---

## Architecture Summary

The project is built on a clean layered architecture following the Dependency Inversion Principle:

1. **API Routes (`app/api/routes/`)**: Handles HTTP requests, parameter validation, rate limiting, and status codes.
2. **Security & Auth Layer (`app/core/security.py`, `app/api/deps.py`)**: Argon2id password hashing, JWT issue/decode, and role verification (`user` vs `admin`).
3. **Services (`app/services/`)**: Orchestrates business logic, file storage, and detector execution.
4. **Detector Abstraction (`app/services/`)**: Standard interface (`BaseDetector`) allowing seamless switching between `DummyDetector` (mock data, no GPU) and `YoloDetector` without altering routes or services.
5. **Database & Storage (`app/db/`, `app/models/`, `uploads/`)**: Relational database persistence (User, Job, Detection, Alert) and local/cloud storage management.

For comprehensive architectural diagrams, request lifecycles, authentication flows, and database ER diagrams, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Folder Structure

```
vision-api/
├── alembic/                    # Alembic database migration scripts & configuration
│   ├── env.py                  # Migration environment configured with app Settings & models
│   ├── script.py.mako          # Template for generating new migrations
│   └── versions/               # Versioned migration revision files
├── alembic.ini                 # Alembic configuration file
├── app/                        # Application source package
│   ├── __init__.py
│   ├── main.py                 # Application factory (create_app), lifespan, CORS, and routers
│   ├── core/                   # Application-wide core modules
│   │   ├── __init__.py
│   │   ├── config.py           # Pydantic Settings class loading from .env
│   │   ├── limiter.py          # Shared slowapi rate limiter instance
│   │   ├── logging.py          # Structured JSON logging setup (no print statements)
│   │   └── security.py         # Argon2id password hashing & PyJWT token utilities
│   ├── api/                    # API routing & dependency layer
│   │   ├── __init__.py
│   │   ├── deps.py             # get_current_user and require_role dependencies
│   │   └── routes/             # Route handlers
│   │       ├── __init__.py
│   │       ├── auth.py         # /auth/register, /auth/login, /auth/refresh
│   │       ├── health.py       # GET /health health-check & DB connectivity endpoint
│   │       └── users.py        # GET /users/me, GET /users/ (admin only)
│   ├── models/                 # Database ORM models (SQLAlchemy 2.0)
│   │   ├── __init__.py         # Exports Base, User, Job, Detection, Alert
│   │   ├── user.py             # User accounts, hashed passwords, roles
│   │   ├── job.py              # Asynchronous image/video processing jobs
│   │   ├── detection.py        # Object detection results & bounding boxes
│   │   └── alert.py            # Event alerts and notifications
│   ├── schemas/                # Pydantic schemas and Data Transfer Objects (DTOs)
│   │   ├── __init__.py         # Exports UserCreate, UserOut, Token, RefreshRequest
│   │   ├── token.py            # Token and RefreshRequest schemas
│   │   └── user.py             # UserCreate and UserOut schemas
│   ├── services/               # Business logic and detector abstractions
│   └── db/                     # Database engine, session maker, and Base
│       ├── __init__.py
│       ├── base.py             # DeclarativeBase definition
│       └── session.py          # Engine, SQLite PRAGMA hook, and get_db() dependency
├── scripts/                    # Command-line administrative scripts
│   ├── __init__.py
│   └── create_admin.py         # Admin bootstrapping and promotion utility
├── tests/                      # Automated test suite
│   ├── __init__.py
│   ├── conftest.py             # Isolated in-memory SQLite fixture & TestClient
│   ├── test_auth.py            # Registration, login, token, RBAC, and rate limit tests
│   ├── test_health.py          # Pytest suite validating /health endpoint & degraded state
│   └── test_models.py          # Pytest suite verifying ORM models & constraints
├── docs/                       # Architectural and technical documentation
│   └── ARCHITECTURE.md         # System design, request flow, auth flow, and ER diagram
├── uploads/                    # Local storage for uploaded images and videos (git-ignored)
├── models_store/               # Directory for model weights (.pt, .onnx) (git-ignored)
├── requirements.txt            # Pinned base application dependencies
├── requirements-cv.txt         # Future CV/ML dependencies for partner handoff
├── .env.example                # Sample environment variable template
├── .gitignore                  # Git exclusions for venv, db, weights, caches
└── README.md                   # Project documentation, setup guide, and roadmap
```

---

## Setup & Getting Started

### Prerequisites
- Python 3.10+ (Tested on Python 3.14)

### 1. Windows (PowerShell)

```powershell
# 1. Clone repository and navigate to root
cd path\to\vision-api

# 2. Create virtual environment
py -m venv .venv

# 3. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Install base dependencies
pip install -r requirements.txt

# 5. Create local environment configuration
Copy-Item .env.example .env

# 6. Apply database migrations
alembic upgrade head

# 7. Start development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. macOS / Linux (Bash / Zsh)

```bash
# 1. Clone repository and navigate to root
cd path/to/vision-api

# 2. Create virtual environment
python3 -m venv .venv

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install base dependencies
pip install -r requirements.txt

# 5. Create local environment configuration
cp .env.example .env

# 6. Apply database migrations
alembic upgrade head

# 7. Start development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Verify Application

- **Interactive API Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## Authentication & Role-Based Access Control

The template provides complete user registration, authentication, token refresh, and role-based access control.

### Endpoints

| Method | Endpoint | Access | Rate Limit | Description |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | Public | 10/min | Register a new user account with role `'user'`. |
| `POST` | `/auth/login` | Public | 5/min | OAuth2 password form (`username` accepts email or username). Returns Token pair. |
| `POST` | `/auth/refresh` | Public | None | Exchange a valid refresh token for a new access/refresh token pair. |
| `GET` | `/users/me` | Authenticated | None | Retrieve authenticated user profile information. |
| `GET` | `/users/` | Admin only | None | List all registered users in the database. |

### Generating a Secure `SECRET_KEY`

Never use the default placeholder secret in production. Generate a cryptographically secure random key:

```bash
# Windows
py -c "import secrets; print(secrets.token_urlsafe(32))"

# macOS / Linux
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the generated 32-byte string into your `.env` file:
```env
SECRET_KEY=your_generated_random_secret_key_here
```
At server startup, the application inspects `SECRET_KEY` and logs a warning if it is empty or still set to the placeholder value.

### Using the Swagger UI Authorize Button

1. Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) in your browser.
2. Click the green **Authorize** button on the top right.
3. In the modal dialog:
   - **Username**: Enter your registered `username` or `email`.
   - **Password**: Enter your plain password.
4. Click **Authorize** and then **Close**.
5. All subsequent requests in the documentation (such as `/users/me` or `/users/`) will automatically include your Bearer access token in the `Authorization` header.

### Creating an Administrator Account

Public registration (`POST /auth/register`) strictly sets user roles to `"user"` to prevent privilege escalation.

To bootstrap an administrator or promote an existing user, run the interactive CLI utility:

```bash
# Windows
py -m scripts.create_admin

# macOS / Linux
python3 -m scripts.create_admin
```

The script prompts for the user's email and username, securely accepts the password via Python's `getpass` module without echoing it to the terminal, and creates the admin account. If the user already exists in the database, it prompts to promote their role to `"admin"`.

### Password Strength Policy

User registration (`POST /auth/register`) and administrative account creation (`scripts/create_admin.py`) enforce a standardized password complexity policy defined by `validate_password_strength()`:
- **Length**: Minimum 8 characters (`PASSWORD_MIN_LENGTH`), maximum 128 characters (`PASSWORD_MAX_LENGTH`).
- **Uppercase**: At least one uppercase letter (`A-Z`).
- **Lowercase**: At least one lowercase letter (`a-z`).
- **Digit**: At least one digit (`0-9`).
- **Special Character**: At least one punctuation character (any in `string.punctuation`, e.g. `!@#$%^&*`).

Key behaviors:
- **Comprehensive Error Reporting**: If a submitted password fails multiple rules, `POST /auth/register` returns `HTTP 422 Unprocessable Entity` listing all unmet rules at once.
- **Login Compatibility**: Password complexity rules are strictly evaluated during registration and account creation. They are **not** evaluated during login (`POST /auth/login`), preserving full backward compatibility for existing user accounts.
- **Credential Redaction**: A custom `RequestValidationError` exception handler strips all submitted plaintext password values from HTTP 422 responses and internal logs.

### Known Limitations

- **Stateless Tokens**: Refresh tokens are signed JWTs with expiration claims. They are currently stateless and cannot be revoked prior to expiration. Token revocation blocklists (e.g., using Redis or database token versions) will be added in Step 7 (Hardening).
- **WebSocket Push In-Process Scope**: WebSocket push feeds and connection tracking operate entirely within a single ASGI server process via an in-memory manager (`WebSocketManager`). Multi-node clusters or multi-worker deployments will require an external message broker (such as Redis Pub/Sub) to fan out alerts across instances.
- **Alert Deduplication**: Alerts are not deduplicated across separate image or video uploads (each qualifying detection triggers an alert); only live camera stream frames enforce a per-user cooldown window (`ALERT_COOLDOWN_SECONDS`).

---

## Detection API

The image detection API provides synchronous object detection with automatic threadpool offloading, streaming upload safeguards, and persistent history tracking.

### Endpoints

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/detect/image` | Authenticated | Upload single image (`multipart/form-data`), run detector, store record in database, return bounding boxes and latency (`201 Created`). |
| `GET` | `/detect/history` | Authenticated | List detection records newest first. Supports pagination with `page` (default 1) and `limit` (default 20, max 100). Admins see all detections. |
| `GET` | `/detect/{detection_id}` | Authenticated | Retrieve detection record by ID. Returns `404 Not Found` if nonexistent or owned by another non-admin user. |

### Upload Security Controls
- **MIME Enforcement**: Uploads must match `ALLOWED_IMAGE_TYPES` (`image/jpeg`, `image/png`, `image/webp`), else rejected with `HTTP 415 Unsupported Media Type`.
- **Early Stream Cutoff**: Upload streams are chunked (64 KB). As soon as the byte counter exceeds `MAX_UPLOAD_MB` (default 10 MB), processing aborts immediately with `HTTP 413 Content Too Large` without buffering oversized files into memory.
- **Pillow Verification**: Every file is inspected with `Image.open().verify()` to detect malformed byte streams or decompression bombs (`HTTP 400 Bad Request`).
- **Dimension Guards**: Images exceeding `MAX_IMAGE_DIMENSION` (default 6000px on either side) are rejected with `HTTP 400`.
- **Sanitized Filenames**: Client-supplied filenames (such as path traversal attempts `../../evil.jpg`) are completely ignored. Files are saved strictly as `UPLOAD_DIR/images/<uuid4>.<ext>`, where `<ext>` is derived from Pillow's verified format.

---

## Video and Background Jobs

The platform supports asynchronous video processing via an in-process `ThreadPoolExecutor`. Videos are uploaded, validated for container integrity and size, persisted under sanitized UUID paths, and processed frame-by-frame in background worker threads without blocking incoming HTTP traffic.

### Endpoints

| Method | Endpoint | Access | Status Code | Description |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/detect/video` | Authenticated | `202 Accepted` | Upload video file (`multipart/form-data`) with optional `frame_skip` query parameter (1–60, default from `FRAME_SKIP`). Enforces per-user active job limit (`MAX_ACTIVE_JOBS_PER_USER`). Returns `{job_id, status: "pending", progress: 0, created_at}`. |
| `GET` | `/jobs/{job_id}` | Authenticated | `200 OK` / `404 Not Found` | Retrieve status, progress (0–100), timestamps, and error for a specific job. Result object is exposed only once `status == "done"`. Restricted to the job owner or administrators (`404 Not Found` for unauthorized users). |
| `GET` | `/jobs` | Authenticated | `200 OK` | List jobs for the authenticated user ordered newest first. Supports pagination (`page` default 1, `limit` default 20, max 100) and an optional `status` filter (`pending`, `running`, `done`, `failed`). Admins can view all jobs across all users. |

### Job Statuses

The background job runner coordinates video jobs through four lifecycle states:
- **`pending`**: The video upload has passed security checks, the `Job` record has been persisted with `progress=0`, and the task has been enqueued in the `ThreadPoolExecutor`.
- **`running`**: A background worker thread has picked up the job, initialized the frame reader, and is running inference on sampled frames. Progress (0–99%) is updated in the database at most once per second or upon each 5% milestone to minimize SQLite write contention.
- **`done`**: All sampled frames have been processed. The job's `progress` is set to 100, and `Job.result` is populated with a `summary` (total frames, processed frames, fps, duration, peak/average object counts), a downsampled `timeline` (maximum 500 data points), and `peak_frame` data. A corresponding `Detection` record (`source_type="video"`) is also inserted.
- **`failed`**: The job encountered an unhandled exception or decode failure, or the server was restarted while the job was in flight. A sanitized user-friendly error message is stored in `Job.error` (e.g., `"Processing failed"` or `"Server restarted while the job was running"`), protecting internal server paths and tracebacks from exposure.

### Video Validation & Container Detection
- **Streaming Upload Limit**: Uploads are read in 64 KB chunks and aborted immediately with `HTTP 413 Content Too Large` if they exceed `MAX_VIDEO_UPLOAD_MB` (default 100 MB).
- **MIME & Container Whitelist**: Files must match `ALLOWED_VIDEO_TYPES` (`video/mp4`, `video/webm`, `video/quicktime`, `video/x-msvideo`), else rejected with `HTTP 415 Unsupported Media Type`.
- **Container Magic Bytes Inspection**: File headers are inspected directly without third-party decoding libraries:
  - **MP4 / MOV**: Checks for `b"ftyp"` at byte offsets 4–8. Brand `b"qt  "` assigns `.mov`, otherwise `.mp4`.
  - **WebM / MKV**: Checks for EBML header `1A 45 DF A3` and assigns `.webm`.
  - **AVI**: Checks for `b"RIFF"` at offsets 0–4 and `b"AVI "` at offsets 8–12 and assigns `.avi`.
  - Any unrecognized container signature is rejected immediately with `HTTP 400 Bad Request` ("Not a valid video file").
- **Path Sanitization**: Client-provided filenames (such as `../../evil.mp4`) are strictly ignored. Videos are saved as `UPLOAD_DIR/videos/<uuid4>.<ext>`.

---

## Alerts

The vision-api platform provides real-time threshold monitoring on computer vision detections across images, video jobs, and live camera streams.

### Thresholds & Evaluation
- **Threshold Rules**:
  - `total_count >= ALERT_CRITICAL_THRESHOLD` (default 20): Creates an `Alert` with level `"critical"`.
  - `total_count >= ALERT_WARNING_THRESHOLD` (default 10): Creates an `Alert` with level `"warning"`.
  - `total_count < ALERT_WARNING_THRESHOLD`: No alert is created (`evaluate_detection()` returns `None`).
- **Human-Readable Notification**: Format example: `"23 objects detected (critical threshold 20)"`.
- **Relational Linkage**: Every `Alert` row is linked to `user_id` and the associated `detection_id`.
- **Fail-Safe Processing**: Alert evaluation is wrapped in `try/except` shields in both synchronous routes (`POST /detect/image`) and asynchronous background workers (`JobRunner`). An alert persistence or broadcast failure **never** fails the parent detection request or video processing job.
- **Testing with DummyDetector**: Since `DummyDetector` produces 2–4 simulated objects per image/frame, set `ALERT_WARNING_THRESHOLD=2` in your `.env` file to immediately observe warning alerts in development.

### Endpoints

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/alerts` | Authenticated | Paginated alert feed ordered newest first (`page` default 1, `limit` default 20, max 100). Optional query filters: `level` (`warning`, `critical`) and `is_read` (`true`, `false`). Owners see their own alerts; administrators see all alerts. |
| `GET` | `/alerts/unread-count` | Authenticated | Returns `{ "unread_count": <int> }` for the authenticated caller (or across the platform for admins). |
| `PATCH` | `/alerts/{alert_id}/read` | Authenticated | Marks a specific alert as read (`is_read = true`). Returns `404 Not Found` if the alert does not exist or belongs to another user. |
| `POST` | `/alerts/read-all` | Authenticated | Bulk marks all unread alerts belonging to the caller as read. Returns `{ "marked_read": <int> }`. |

---

## Analytics

The analytics module provides aggregation metrics and continuous timeline data across historical detections.

### Endpoints

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/analytics/summary` | Authenticated | Summary statistics over a date range: `total_detections`, `total_objects`, `avg_count`, `max_count`, `counts_by_source_type` (`image`, `video`, `stream`), `alerts_by_level` (`warning`, `critical`), `top_labels` (count per detected label taken from `results.objects` or `results.peak_frame.objects`), and `truncated` flag. |
| `GET` | `/analytics/timeseries` | Authenticated | Chronological buckets `{bucket_start, detections, avg_count, max_count}` partitioned by `interval=hour` (default) or `interval=day`. Pre-fills empty buckets with zeroes to ensure gap-free timeline rendering. |

### Parameters & Validation
- **`date_from` & `date_to`**: ISO-8601 datetimes (e.g. `2026-10-24T12:00:00Z`). Default: the preceding 7 days up to `now`.
- **Validation**:
  - `date_from > date_to`: Rejection with `HTTP 422 Unprocessable Entity` ("date_from cannot be after date_to").
  - Date range > `ANALYTICS_MAX_RANGE_DAYS` (default 90 days): Rejection with `HTTP 422` ("Date range exceeds maximum allowed limit").
  - Invalid interval (values other than `hour` or `day`): Rejection with `HTTP 422`.
- **Database Portability & Truncation**: To remain 100% portable across both SQLite and PostgreSQL without database-specific datetime functions, the API loads at most `ANALYTICS_MAX_ROWS` (default 5,000) detections within the range and aggregates metrics in Python. If the row limit is reached, the response includes `"truncated": true`.
- **Access Scoping**: Standard users view analytics computed exclusively over their own detections; administrators view platform-wide aggregated metrics.

---

## Real-time WebSocket

Real-time capabilities are provided via two dedicated WebSocket endpoints:
1. **`/ws/alerts`**: Live alert notification feed.
2. **`/ws/stream`**: High-frequency binary video frame ingestion with computer vision inference.

### Security & Handshake Rules
- **First-Message Authentication**: To prevent token leakage in web server access logs and query strings, tokens are **never** passed in the URL. Clients connect and must transmit an initial JSON authentication payload within `WS_AUTH_TIMEOUT_SECONDS` (default 5.0s):
  ```json
  {"type": "auth", "token": "<access_token>"}
  ```
  - **Success**: Server replies with `{"type": "auth_ok"}`.
  - **Failure / Timeout**: Server closes the socket immediately with close code `4401`. Access tokens are validated identically to HTTP endpoints (signature, expiration, and `is_active` status).
- **Origin Header Verification**: Validates incoming `Origin` headers against `ALLOWED_ORIGINS` and the request `Host` header. Non-browser clients without an `Origin` header are permitted. Disallowed origins are closed immediately with code `4403`.
- **Connection Throttling**: Users are restricted to `WS_MAX_CONNECTIONS_PER_USER` (default 3) concurrent connections across all channels. Attempts exceeding this limit are rejected with close code `4429`.

### Message Formats

#### 1. Alert Feed (`WS /ws/alerts`)
- **Server Push (Alert Event)**: Pushed whenever an alert is created for the authenticated user (or for all users if the client is an admin):
  ```json
  {
    "type": "alert",
    "alert": {
      "id": 42,
      "user_id": 1,
      "detection_id": 105,
      "level": "critical",
      "message": "23 objects detected (critical threshold 20)",
      "is_read": false,
      "created_at": "2026-10-25T15:30:00Z"
    }
  }
  ```
- **Ping / Pong**: Clients can send `{"type": "ping"}`; the server replies `{"type": "pong"}`. All other incoming text messages are safely ignored.

#### 2. Live Video Stream (`WS /ws/stream`)
- **Binary Frame Transmission**: Clients send raw image bytes (JPEG or PNG) as binary WebSocket frames.
- **Size Limit**: Frames larger than `WS_MAX_FRAME_KB` (default 2,048 KB / 2 MB) are rejected with a JSON error, and the connection remains open:
  ```json
  {"type": "error", "message": "Frame size exceeds 2048 KB limit"}
  ```
- **Pillow Decode Error Tolerance**: If corrupt or unreadable image bytes are received, the server replies with an error message and continues processing subsequent frames without crashing:
  ```json
  {"type": "error", "message": "Failed to decode image frame"}
  ```
- **"Latest Frame Wins" Flow Control**: Ingestion and inference run in two decoupled asynchronous coroutines:
  - An ingestion coroutine continuously reads incoming binary frames and stores the most recent frame into a single-frame buffer, replacing any unread frame and incrementing a skipped counter.
  - An inference worker coroutine picks up the latest frame, offloads detector inference to a threadpool (`run_in_threadpool`), and transmits results back to the client:
    ```json
    {
      "type": "detections",
      "frame_id": 12,
      "skipped_since_last": 1,
      "result": {
        "objects": [
          {"label": "person", "confidence": 0.89, "bbox": {"x1": 10.5, "y1": 20.0, "x2": 150.2, "y2": 320.1}}
        ],
        "total_count": 1,
        "inference_ms": 14.2,
        "detector_name": "dummy"
      }
    }
    ```
- **Stream Alert Cooldown**: To avoid database bloat and alert spam during live camera streaming, stream frame alerts enforce a per-user cooldown of `ALERT_COOLDOWN_SECONDS` (default 30s). When a stream frame triggers an alert, exactly one `Detection` row (`source_type="stream"`, `file_path=None`) is persisted and linked to the new `Alert`. Non-alert stream frames are not stored in the database.

### Developer Manual Test Bench (`GET /ws-test`)

When `DEBUG=true` in `.env`, navigating to [http://127.0.0.1:8000/ws-test](http://127.0.0.1:8000/ws-test) opens a self-contained, interactive HTML/JS diagnostic workbench:
- Login form calling `POST /auth/login` and storing the JWT in memory.
- Connect button for `/ws/alerts` showing live logs and ping/pong latency.
- File picker to send test JPEG/PNG binary frames to `/ws/stream` and view bounding box JSON.
- "Use Webcam" toggle streaming 1 frame per second from your camera using HTML5 `navigator.mediaDevices.getUserMedia` and canvas JPEG encoding.
- When `DEBUG=false`, `GET /ws-test` returns `HTTP 404 Not Found`.

### Frontend JavaScript Integration Example

Copy-pasteable code snippet for frontend web clients:

```javascript
// 1. Establish WebSocket connection
const wsUrl = `ws://${window.location.host}/ws/alerts`;
const socket = new WebSocket(wsUrl);

socket.onopen = () => {
  console.log("WebSocket connected. Sending initial auth message...");
  // 2. Mandatory First-Message Authentication within 5 seconds
  socket.send(JSON.stringify({
    type: "auth",
    token: localStorage.getItem("access_token")
  }));
};

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === "auth_ok") {
    console.log("Authenticated successfully!");
    // Start keepalive heartbeat every 30 seconds
    setInterval(() => socket.send(JSON.stringify({ type: "ping" })), 30000);
  } else if (data.type === "alert") {
    console.warn(`[ALERT ${data.alert.level.toUpperCase()}]: ${data.alert.message}`);
    showNotificationBanner(data.alert);
  } else if (data.type === "pong") {
    console.log("Heartbeat acknowledged by server");
  }
};

socket.onclose = (event) => {
  console.log(`WebSocket closed (code: ${event.code}, reason: ${event.reason})`);
  if (event.code === 4401) {
    console.error("Authentication expired or invalid. Please re-login.");
  }
};

// 3. Streaming binary frames to /ws/stream (e.g. from an HTML5 canvas)
async function sendCanvasFrame(streamSocket, canvas) {
  canvas.toBlob((blob) => {
    if (blob && streamSocket.readyState === WebSocket.OPEN) {
      blob.arrayBuffer().then((buffer) => streamSocket.send(buffer));
    }
  }, "image/jpeg", 0.8);
}
```

---

## Configuration Reference

The following environment variables configure application behavior in `.env`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DEBUG` | `true` | Enables debug logging and exposes developer bench `/ws-test`. Set `false` in production. |
| `ALERT_WARNING_THRESHOLD` | `10` | Object count threshold to trigger warning alerts (`level="warning"`). Set to `2` to test with DummyDetector. |
| `ALERT_CRITICAL_THRESHOLD` | `20` | Object count threshold to trigger critical alerts (`level="critical"`). |
| `ALERT_COOLDOWN_SECONDS` | `30.0` | Throttling window in seconds between stream alerts for a user. |
| `WS_AUTH_TIMEOUT_SECONDS` | `5.0` | Time allowed for clients to send initial `{"type": "auth"}` message. |
| `WS_MAX_FRAME_KB` | `2048` | Maximum allowed binary frame size for `/ws/stream` (2 MB). |
| `WS_MAX_CONNECTIONS_PER_USER` | `3` | Maximum concurrent open WebSocket connections allowed per user. |
| `ANALYTICS_MAX_ROWS` | `5000` | Maximum historical detection rows evaluated for in-memory analytics. |
| `ANALYTICS_MAX_RANGE_DAYS` | `90` | Maximum date query range allowed in analytics endpoints. |
| `MAX_UPLOAD_MB` | `10` | Maximum allowed image upload size in MB. |
| `MAX_VIDEO_UPLOAD_MB` | `100` | Maximum allowed video upload size in MB. |
| `MAX_CONCURRENT_JOBS` | `2` | Maximum worker threads in background video `ThreadPoolExecutor`. |
| `MAX_ACTIVE_JOBS_PER_USER` | `3` | Maximum active (`pending` + `running`) video jobs per user. |
| `FRAME_SKIP` | `5` | Default video frame sampling skip interval (e.g., process every 5th frame). |
| `DETECTOR_BACKEND` | `dummy` | Active vision detector backend (`dummy` or `yolo`). |
| `RATE_LIMIT_ENABLED` | `true` | Enables slowapi IP request rate limiting. |

---

## Plugging in a Real Detector (for the Partner)

The template is decoupled from ML frameworks by design. The base environment operates with `DummyDetector` without requiring PyTorch, CUDA, or OpenCV.

When the ML/CV partner is ready to integrate a real YOLO detector, follow these exact steps:

### Step 1: Implement `YoloDetector`
Open `app/services/detector/yolo_detector.py`:
- In `load()`: perform a **lazy import** of Ultralytics (`from ultralytics import YOLO`), load weights from `self.model_path`, and set `self._is_loaded = True`.
- In `detect(image)`: run inference on the incoming RGB PIL Image (`results = self.model(image, conf=self.confidence_threshold)`), measure elapsed milliseconds with `time.perf_counter()`, map boxes `(x1, y1, x2, y2)` and labels into `DetectedObject` instances, and return a validated `DetectionResult`.
- Ensure no ML dependencies (`torch`, `ultralytics`, `cv2`, `numpy`) are imported at module top-level!

### Step 2: Implement `OpenCVFrameReader` for Real Video Decoding
Open `app/services/video/opencv_reader.py`:
- In `open(path)`:
  - Perform a **lazy import** of OpenCV (`import cv2`) inside `open()`—never at module top-level!
  - Initialize `self.cap = cv2.VideoCapture(path)`.
  - Validate that `self.cap.isOpened()`.
  - Read video properties:
    - `self._fps = float(self.cap.get(cv2.CAP_PROP_FPS)) or 25.0`
    - `self._total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))`
    - `self._width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))`
    - `self._height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))`
- In `iter_frames(frame_skip)`:
  - Loop over video frames up to `total_frames`.
  - Read frame via `ret, frame = self.cap.read()`.
  - Advance position by `frame_skip`.
  - Convert frame from BGR to RGB: `rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)`.
  - Wrap into a PIL Image: `pil_img = Image.fromarray(rgb)`.
  - Calculate timestamp: `timestamp_s = frame_idx / self._fps`.
  - Yield `(frame_idx, timestamp_s, pil_img)`.
- In `close()`:
  - Safely release the capture handle: `if self.cap: self.cap.release()`.

### Step 3: Install ML & Video Dependencies
Install the dedicated CV requirements:
```bash
pip install -r requirements-cv.txt
```

### Step 4: Add Model Weights
Place your trained or pretrained YOLO weights (e.g., `yolov8n.pt`) inside the `models_store/` directory:
```bash
# Example
models_store/
├── .gitkeep
└── yolov8n.pt
```
> [!IMPORTANT]
> Model weights are excluded by `.gitignore` (`models_store/*` and `*.pt`). Never commit binary model weights to the Git repository.

### Step 5: Configure Environment
Update your `.env` file to switch both the detector and frame reader backends:
```env
DETECTOR_BACKEND=yolo
MODEL_PATH=models_store/yolov8n.pt
CONFIDENCE_THRESHOLD=0.25
FRAME_READER_BACKEND=opencv
```

### Step 6: Verify with Tests
Run the test suite to verify your detector and frame reader integrate seamlessly:
```bash
pytest
```
Restart the server, check `GET /health` (`"detector": "yolo"`, `"model_loaded": true`, `"detector_is_placeholder": false`), and test `POST /detect/image` and `POST /detect/video`.

---

## Known Limitations

- **In-Process Thread Pool**: Background video jobs run inside an in-process `ThreadPoolExecutor`. If the server is restarted while jobs are pending or running, they do not survive and are automatically marked as `failed` ("Server restarted while the job was running") during application startup reconciliation.
- **No Job Cancellation**: There is currently no endpoint or mechanism to cancel or abort an in-flight background job.
- **Single Process Uvicorn Runner**: Do not run multiple Uvicorn worker processes (`--workers > 1`) with this in-process runner, as background tasks will be isolated to individual process memory spaces. For multi-process or distributed production setups, a distributed task queue (e.g., Celery with Redis) should be used.
- **Synthetic Dummy Frame Reader**: In base development mode (`FRAME_READER_BACKEND=dummy`), `DummyFrameReader` generates synthetic solid-color frames with simulated delay and does not decode real video frames.
- **Stateless Tokens**: Refresh tokens are signed JWTs with expiration claims. They are currently stateless and cannot be revoked prior to expiration. Token revocation blocklists (e.g., using Redis or database token versions) will be added in Step 7 (Hardening).

---

## Database and Migrations

Alembic manages all database schema migrations. Schema creation is strictly owned by Alembic migrations rather than runtime `create_all()` calls.

### Applying Migrations
To bring your database schema up to date with the latest revisions:
```bash
alembic upgrade head
```

### Creating New Migrations
When you modify or add SQLAlchemy models in `app/models/`, generate a new migration revision:
```bash
alembic revision --autogenerate -m "describe_schema_changes"
```
Alembic automatically detects added tables, columns, indexes, and constraints. Always inspect the newly created file under `alembic/versions/` before applying.

### Switching to PostgreSQL in Production
The application is preconfigured with generic types (such as `JSON` and `DateTime(timezone=True)`) compatible with both SQLite and PostgreSQL.

To migrate to PostgreSQL:
1. Install a PostgreSQL driver in your environment:
   ```bash
   pip install psycopg2-binary
   ```
2. Update `DATABASE_URL` in your `.env` file:
   ```env
   DATABASE_URL=postgresql://myuser:mypassword@localhost:5432/vision_api
   ```
3. Run Alembic migrations against PostgreSQL:
   ```bash
   alembic upgrade head
   ```

---

## Running Tests

Run the automated test suite with pytest (executed against an isolated in-memory SQLite database):

```bash
# Activate virtual environment first, then run:
pytest
```

To run with verbose output:
```bash
pytest -v
```

---

## Roadmap

- [x] **Step 1: Scaffold, docs, config, health check**
- [x] **Step 2: Database and migrations**
- [x] **Step 3: Authentication and roles**
- [x] **Step 4: Detection API with DummyDetector**
- [x] **Step 5: Video upload and background jobs**
- [x] **Step 6: WebSocket, analytics, alerts**
- [ ] **Step 7: Error handling and hardening**
- [ ] **Step 8: Docker and partner handoff**

---

## Changelog

### Step 6 — Alerts, Analytics & Real-Time WebSocket
- Added Step 6 configuration in `app/core/config.py`, `.env.example`, and `.env`: `ALERT_WARNING_THRESHOLD=10`, `ALERT_CRITICAL_THRESHOLD=20`, `ALERT_COOLDOWN_SECONDS=30`, `WS_AUTH_TIMEOUT_SECONDS=5`, `WS_MAX_FRAME_KB=2048`, `WS_MAX_CONNECTIONS_PER_USER=3`, `ANALYTICS_MAX_ROWS=5000`, `ANALYTICS_MAX_RANGE_DAYS=90`.
- Built alert evaluation and dispatch service in `app/services/alert_service.py`:
  - Threshold evaluation creating `Alert` rows at `"critical"` and `"warning"` levels with human-readable notifications.
  - Linked to `user_id` and `detection_id`, committed, and pushed thread-safely via WebSocket.
  - Shielded with `try/except` inside `POST /detect/image` and video worker `process_video_job` so alert errors never fail detection requests.
- Implemented Alert API routes in `app/api/routes/alerts.py`:
  - `GET /alerts`: Paginated history (`page`, `limit`), newest first, with optional `level` and `is_read` filters.
  - `GET /alerts/unread-count`: Returns unread count for current user (or global for admins).
  - `PATCH /alerts/{alert_id}/read`: Marks a single alert as read with ownership enforcement (404 for other users).
  - `POST /alerts/read-all`: Bulk marks all unread alerts for caller as read.
- Implemented portable Analytics routes in `app/api/routes/analytics.py`:
  - `GET /analytics/summary`: Aggregate metrics (`total_detections`, `total_objects`, `avg_count`, `max_count`, `counts_by_source_type`, `alerts_by_level`, `top_labels`) computed in Python over at most `ANALYTICS_MAX_ROWS` rows for cross-database portability; returns `"truncated": true` if row limit is reached.
  - `GET /analytics/timeseries`: Gap-free continuous time buckets partitioned by `interval=hour` or `interval=day` with empty buckets filled with zeroes.
  - Validations enforcing `date_from <= date_to`, max range `ANALYTICS_MAX_RANGE_DAYS`, and interval whitelist (HTTP 422).
- Designed in-process WebSocket connection manager in `app/services/ws_manager.py`:
  - Per-user and per-role connection tracking with channel isolation (`alerts` vs `stream`).
  - Safe broadcasting dropping broken sockets without interrupting other clients.
  - Cross-thread alert dispatching via `asyncio.run_coroutine_threadsafe` using ASGI event loop captured at startup.
  - Enforced `WS_MAX_CONNECTIONS_PER_USER` throttling.
- Implemented real-time WebSocket endpoints in `app/api/routes/ws.py`:
  - First-message authentication (`{"type": "auth", "token": "..."}`) within `WS_AUTH_TIMEOUT_SECONDS` (close code 4401 on failure), preventing URL token leakage.
  - Origin header enforcement (close code 4403 on forbidden origin).
  - `WS /ws/alerts`: Pushes `{"type": "alert", "alert": {...}}` to user/admin subscribers with ping/pong keepalive.
  - `WS /ws/stream`: Ingests binary JPEG/PNG frames; enforces `WS_MAX_FRAME_KB` and non-crashing Pillow decode error handling; uses decoupled latest-frame-wins flow control with dropped frame reporting (`skipped_since_last`); enforces stream alert cooldown `ALERT_COOLDOWN_SECONDS` and persists a single `Detection` record (`source_type="stream"`) upon alert trigger.
- Implemented developer manual test bench `GET /ws-test` in `app/api/routes/test_page.py` (active only when `DEBUG=true`, returns 404 otherwise).
- Updated `GET /health` with `ws_connections` counter reporting total open sockets.
- Added comprehensive pytest test suites in `tests/test_alerts.py`, `tests/test_analytics.py`, and `tests/test_ws.py` (82 total tests passing).

### Authentication Improvement — Stronger Password Rules
- Added reusable `validate_password_strength(password)` in `app/core/security.py` with `PASSWORD_MIN_LENGTH=8` and `PASSWORD_MAX_LENGTH=128`.
- Enforces 6 security rules: minimum 8 characters, maximum 128 characters, at least 1 uppercase letter, 1 lowercase letter, 1 digit, and 1 special character (`string.punctuation`).
- Added Pydantic `@field_validator("password")` to `UserCreate` (`app/schemas/user.py`) returning `HTTP 422` listing all unmet rules simultaneously, with rules documented in OpenAPI `/docs` schema description.
- Updated `scripts/create_admin.py` to loop and re-prompt until a valid password meeting all rules is supplied and confirmed.
- Registered custom `RequestValidationError` exception handler in `app/main.py` ensuring submitted passwords are stripped from HTTP 422 error details and never logged.
- Maintained legacy user authentication compatibility on `POST /auth/login` without altering password hashing or database schemas.
- Updated existing tests to use compliant passwords (`Str0ng!Pass`) and added comprehensive test scenarios covering each rule individually, combined multi-rule failure, 422 password redaction, and legacy user login.

### Step 5 — Video Upload, Background Jobs & Job Status
- Added video and background job configuration in `app/core/config.py`, `.env`, and `.env.example`: `MAX_VIDEO_UPLOAD_MB=100`, `ALLOWED_VIDEO_TYPES`, `FRAME_SKIP=5`, `MAX_CONCURRENT_JOBS=2`, `MAX_ACTIVE_JOBS_PER_USER=3`, `FRAME_READER_BACKEND="dummy"`, `DUMMY_FRAME_DELAY_MS=20`, `JOB_RUNNER_INLINE=false`.
- Created pluggable video frame reader abstraction in `app/services/video/`:
  - `BaseFrameReader` ABC supporting context managers, metadata properties (`fps`, `total_frames`, `width`, `height`), and `iter_frames(frame_skip)` yielding `(frame_index, timestamp_seconds, PIL.Image)`.
  - `DummyFrameReader`: Zero-ML simulation deriving frame count (60–300) from file size, yielding solid-color RGB frames with observable sleep delay.
  - `OpenCVFrameReader`: Stub raising `NotImplementedError` with lazy `cv2` import inside `open()` and comprehensive instructions for partner handoff.
  - `get_frame_reader()` factory dynamically resolving reader backend from configuration.
- Implemented streaming video validation service in `app/services/video_service.py`:
  - Early chunked cutoff enforcing `MAX_VIDEO_UPLOAD_MB` (`HTTP 413`).
  - Empty file detection (`HTTP 400`) and MIME type validation (`HTTP 415`).
  - Container magic bytes inspection (MP4/MOV via `ftyp`/`qt  `, WebM via `\x1a\x45\xdf\xa3`, AVI via `RIFF...AVI `).
  - Sanitized UUID storage ignoring client-supplied paths (`uploads/videos/<uuid4>.<ext>`).
- Built resilient background job runner in `app/services/job_runner.py`:
  - Lifecycle-managed `ThreadPoolExecutor` on `app.state.job_runner`.
  - Synchronous inline execution support when `JOB_RUNNER_INLINE=True` (for testing).
  - Thread-isolated SQLAlchemy sessions using dedicated `SessionLocal()` handles.
  - Rate-limited progress database writes (every 5% or 1 second) preventing SQLite lock contention.
  - Timeline downsampling (capped at 500 points), summary compilation, peak frame tracking, and automatic `Detection` record insertion.
  - Sanitized error handling preventing internal tracebacks from reaching clients.
  - Application startup reconciliation marking orphaned `pending` or `running` jobs as `failed`.
- Implemented API routes:
  - `POST /detect/video`: Authenticated upload with `frame_skip` validation (1–60), active job throttling (`HTTP 429`), detector availability check (`HTTP 503`), and `HTTP 202 Accepted` response.
  - `GET /jobs/{job_id}`: Job status and progress inspection with owner/admin authorization (`HTTP 404` for unauthorized users) and result masking until completion.
  - `GET /jobs`: Paginated user job listing with optional `status` filtering and admin global visibility.
  - Updated `GET /health` with `active_jobs` count.
- Added comprehensive pytest test suite covering frame reader unit tests, container signature detection, video upload validation, job execution lifecycle, async polling, failure recovery, access control, concurrency limits, and startup reconciliation.
- Added Mermaid sequence diagram, state machine diagram, and class diagram to `docs/ARCHITECTURE.md`.

### Step 4 — Detector Interface, DummyDetector & Image Detection API
- Added `Pillow==13.0.0` to `requirements.txt` with pinned version.
- Added upload and detection configuration in `app/core/config.py`, `.env`, and `.env.example`: `CONFIDENCE_THRESHOLD=0.25`, `MAX_UPLOAD_MB=10`, `MAX_IMAGE_DIMENSION=6000`, `ALLOWED_IMAGE_TYPES=image/jpeg,image/png,image/webp`, and `UPLOAD_DIR=uploads`.
- Created Pydantic v2 schemas in `app/schemas/detection.py`: `BoundingBox`, `DetectedObject`, `DetectionResult`, and `DetectionOut` (with `extra` dictionary for detector-specific expansion and `from_attributes=True`).
- Designed modular detector package in `app/services/detector/`:
  - `BaseDetector` ABC with `name`, `is_placeholder`, `is_loaded`, `load()`, `close()`, and `detect(image: Image.Image)` method with developer tips for OpenCV/NumPy integration.
  - `DummyDetector`: Zero-ML deterministic simulated detections seeded by SHA-256 hash of image dimensions and sample pixel bytes, strictly bounded coordinates, confidence filtering, and latency measurement.
  - `YoloDetector`: Clean stub raising `NotImplementedError` with explicit step-by-step TODO instructions for the partner and zero top-level ML imports.
  - `get_detector()` factory: Dynamically instantiates the detector backend specified by `DETECTOR_BACKEND` or raises a clear `ValueError`.
- Updated application lifespan in `app/main.py`: Initialized and loaded detector once at startup into `app.state.detector`, caught and logged load errors, and cleanly closed handles at shutdown.
- Updated `GET /health` in `app/api/routes/health.py`: Added `detector`, `model_loaded`, and `detector_is_placeholder` fields; reports `"degraded"` status if detector failed to load.
- Implemented `app/services/image_service.py`: Enforces MIME validation, early chunked streaming cutoff (HTTP 413), non-empty validation, Pillow `verify()` / reopen / RGB conversion, dimension checks (HTTP 400), and UUID-based disk persistence ignoring client-provided filenames.
- Implemented synchronous threadpool routes in `app/api/routes/detect.py`:
  - `POST /detect/image`: Authenticated upload, validation, inference execution, database persistence, and `HTTP 201 Created` response.
  - `GET /detect/history`: User-scoped paginated history (`page`, `limit`), newest first; administrative global view.
  - `GET /detect/{detection_id}`: Owner-restricted retrieval returning `HTTP 404 Not Found` for unauthorized or missing records.
- Added comprehensive pytest test suite in `tests/test_detector.py` and `tests/test_detect_api.py` covering determinism, bounding box invariants, confidence thresholds, authentication, error handling (400, 413, 415, 503), path traversal protection, and access control isolation.
- Added Mermaid class diagrams and sequence diagrams to `docs/ARCHITECTURE.md`.

### Step 3 — Authentication & Roles
- Added dependencies to `requirements.txt`: `PyJWT==2.15.1`, `argon2-cffi==25.1.0`, `email-validator==2.3.0`, and `slowapi==0.1.10`.
- Updated `Settings` in `app/core/config.py` and `.env.example` with token expiration durations, JWT algorithm, and rate limiting options.
- Configured startup check in `app/main.py` warning if `SECRET_KEY` is empty or set to the default placeholder.
- Implemented Argon2id password hashing and PyJWT token generation/decoding in `app/core/security.py`, including dummy hash verification to neutralize timing attacks.
- Created Pydantic schemas in `app/schemas/` (`UserCreate`, `UserOut`, `Token`, `RefreshRequest`), enforcing username regex and password length constraints while barring client role assignment.
- Built authentication dependencies in `app/api/deps.py`: `get_current_user` (Bearer token resolution) and `require_role` (RBAC checking).
- Added endpoints in `app/api/routes/auth.py` (`/register`, `/login`, `/refresh`) and `app/api/routes/users.py` (`/me`, `/`), supporting OAuth2 form login via email or username and generic 401 error responses.
- Implemented IP-based rate limiting on login (5/min) and registration (10/min) using `slowapi`, configurable via `RATE_LIMIT_ENABLED`.
- Created administrative CLI script in `scripts/create_admin.py` for bootstrapping and promoting admin accounts with `getpass`.
- Added comprehensive unit and integration tests in `tests/test_auth.py` covering registration, login, token refresh, invalid/expired tokens, RBAC enforcement, Argon2 password storage, and rate limiting.
- Documented authentication sequence flow in `docs/ARCHITECTURE.md` and added complete auth setup documentation to `README.md`.

### Step 2 — Database, Models & Migrations
- Added `sqlalchemy==2.1.6` and `alembic==1.20.1` to `requirements.txt` with exact pinned versions.
- Built `app/db/base.py` (`Base = DeclarativeBase`) and `app/db/session.py` with SQLite PRAGMA foreign keys enforcement and `get_db()` dependency generator.
- Implemented four SQLAlchemy 2.0 models with UTC timezone-aware datetimes and portable JSON fields: `User`, `Job`, `Detection`, `Alert`.
- Configured Alembic in project root; modified `alembic/env.py` to read `DATABASE_URL` directly from `Settings` and enabled `render_as_batch=True` for SQLite compatibility.
- Generated and applied initial migration (`ccea8191d3dd_initial_schema.py`) via `alembic upgrade head`.
- Updated `GET /health` with `SELECT 1` connectivity check, returning `"database": "ok"` or `"status": "degraded"`.
- Added test fixtures in `tests/conftest.py` with isolated in-memory SQLite database, unit tests for all models and constraints in `tests/test_models.py`, and verified database health/degraded response handling in `tests/test_health.py`.
- Added database Entity-Relationship (ER) Mermaid diagram to `docs/ARCHITECTURE.md`.

### Step 1 — Scaffold, Docs, Config & Health Check
- Initialized project scaffolding with clean modular structure (`app/`, `tests/`, `docs/`, `uploads/`, `models_store/`).
- Added package initializers (`__init__.py`) and `.gitkeep` markers for empty directories.
- Configured `.gitignore` targeting virtual environments, database files, ML weights, and caches.
- Generated `requirements.txt` with exact pinned versions and created `requirements-cv.txt` documenting future ML requirements.
- Configured `pydantic-settings` in `app/core/config.py` with flexible CORS origin parsing and cached `get_settings()`.
- Implemented structured JSON logging in `app/core/logging.py` without print statements.
- Created `app/main.py` application factory with async lifespan hook, CORS middleware, and beginner documentation.
- Built `GET /health` endpoint in `app/api/routes/health.py` returning service metadata and model load status.
- Added comprehensive unit test in `tests/test_health.py` using FastAPI `TestClient`.
- Authored system architecture and sequence diagrams in `docs/ARCHITECTURE.md`.
