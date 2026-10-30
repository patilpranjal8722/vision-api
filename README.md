# vision-api 🚀

A modular, production-ready, reusable FastAPI backend template designed specifically for computer-vision hackathons and rapid ML prototyping.

The template provides an end-to-end operational backend (validation, storage, asynchronous task coordination, WebSocket feeds, and data persistence) with **zero heavy ML dependencies (no GPU, PyTorch, or OpenCV required during base development)**. A lightweight placeholder detector enables full frontend and infrastructure development until real model weights are plugged in.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Architecture & Documentation Links](#architecture--documentation-links)
- [What This Repo Does Not Contain](#what-this-repo-does-not-contain)
- [Folder Structure](#folder-structure)
- [Quick Start](#quick-start)
  - [Path 1: Local Python Virtualenv (SQLite)](#path-1-local-python-virtualenv-sqlite)
  - [Path 2: Docker Compose (SQLite)](#path-2-docker-compose-sqlite)
  - [Path 3: Docker Compose with PostgreSQL](#path-3-docker-compose-with-postgresql)
- [Container Administration & Persistent Volumes](#container-administration--persistent-volumes)
- [Authentication & Role-Based Access Control](#authentication--role-based-access-control)
- [Detection API](#detection-api)
- [Video Upload & Background Jobs](#video-upload--background-jobs)
- [Alerts, Analytics & WebSockets](#alerts-analytics--websockets)
- [CV Integration](#cv-integration)
- [Running Tests](#running-tests)
- [Roadmap](#roadmap)
- [Changelog](#changelog)

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
- **Containerization & CI**: Docker (`python:3.12-slim`), Docker Compose v2, GitHub Actions CI

---

## Architecture & Documentation Links

Detailed guides for teammates and frontend integrators:

- 📐 **System Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Layered architecture diagrams, request flows, middleware onion, security model, and database ER diagrams.
- 📖 **Frontend API Reference**: [docs/API_REFERENCE.md](docs/API_REFERENCE.md) — Exhaustive REST endpoint table, error formats, rate limits, WebSocket protocols, and a copy-paste JavaScript client.
- 🤝 **Partner Handoff Guide**: [docs/PARTNER_GUIDE.md](docs/PARTNER_GUIDE.md) — Step-by-step instructions for plugging in YOLO and OpenCV, performance optimization, and hackathon adaptation.
- **PPE Detection Contract**: [docs/PPE_CONTRACT.md](docs/PPE_CONTRACT.md) — Formal specification of the ppe.v1 contract, schemas, verdict precedence, and YOLO partner guidelines.
- **CV Integration Contract**: [docs/CV_INTEGRATION_CONTRACT.md](docs/CV_INTEGRATION_CONTRACT.md) — Specification of the v1.0 contract between backend and external CV microservice.
- 📄 **OpenAPI Specification**: [docs/openapi.json](docs/openapi.json) — Static OpenAPI schema exported via `python -m scripts.export_openapi`.

---

## What This Repo Does Not Contain

To keep this template ultra-lightweight, rapid to clone (<5 MB), and universally runnable on any developer laptop without requiring GPU hardware or multi-gigabyte downloads, the base repository intentionally **does NOT contain**:

1. **No ML Model Weights**: No `.pt`, `.onnx`, or `.bin` weight files are committed to this repository. The `models_store/` directory is git-ignored and docker-ignored. Teammates download weights out-of-band (e.g. from Google Drive or S3) and drop them into `models_store/`.
2. **No Heavy ML Frameworks in `requirements.txt`**: PyTorch, TorchVision, Ultralytics, and OpenCV are intentionally absent from base dependencies. They are documented in `requirements-cv.txt`.
3. **No Proprietary Datasets or Videos**: Training data, annotation sets, and video test files are excluded to maintain clean repository hygiene.
4. **Placeholder Simulators**: The base application runs out-of-the-box using `DummyDetector` (simulated bounding boxes using image pixel hashing) and `DummyFrameReader` (synthetic video frames). Your ML partner can plug in real YOLO weights and OpenCV decoding at any time by following [docs/PARTNER_GUIDE.md](docs/PARTNER_GUIDE.md).

---

## Folder Structure

```
vision-api/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI workflow (Python 3.12, pytest, pip-audit)
├── alembic/                    # Alembic database migration scripts & configuration
│   ├── env.py                  # Migration environment configured with app Settings & models
│   ├── script.py.mako          # Template for generating new migrations
│   └── versions/               # Versioned migration revision files
├── alembic.ini                 # Alembic configuration file
├── app/                        # Application source package
│   ├── __init__.py
│   ├── main.py                 # Application factory (create_app), lifespan, CORS, and routers
│   ├── core/                   # Application-wide core modules (config, limiter, logging, security)
│   ├── api/                    # API routing & dependency layer
│   │   ├── deps.py             # get_current_user and require_role dependencies
│   │   └── routes/             # Route handlers (auth, health, users, detect, jobs, alerts, analytics, ws)
│   ├── models/                 # Database ORM models (User, Job, Detection, Alert)
│   ├── schemas/                # Pydantic schemas and Data Transfer Objects (DTOs)
│   ├── services/               # Business logic, inference, job runner, detector, and video readers
│   └── db/                     # Database engine, session maker, and DeclarativeBase
├── docker/
│   └── entrypoint.sh           # Container entrypoint script (migrations + single-worker Uvicorn)
├── docs/                       # Architectural and technical documentation
│   ├── API_REFERENCE.md        # Comprehensive frontend API documentation
│   ├── ARCHITECTURE.md         # System design, request flows, and ER diagrams
│   ├── PARTNER_GUIDE.md        # Partner handoff guide for YOLO and OpenCV integration
│   └── openapi.json            # Exported OpenAPI 3.1 schema
├── models_store/               # Directory for model weights (.pt, .onnx) (git-ignored)
├── scripts/                    # Administrative CLI scripts
│   ├── create_admin.py         # Admin bootstrapping and promotion utility
│   ├── export_openapi.py       # OpenAPI schema export script
│   └── smoke_test.py           # Automated end-to-end smoke test suite
├── tests/                      # Automated pytest test suites
├── uploads/                    # Local storage for uploaded media (git-ignored)
├── .dockerignore               # Container build exclusion list
├── .env.example                # Sample environment variable template
├── .gitattributes              # Git line endings enforcement (LF on scripts, Dockerfile, YAML)
├── .gitignore                  # Git exclusions for venv, db, weights, caches
├── Dockerfile                  # Production container definition (python:3.12-slim, non-root user)
├── docker-compose.yml          # Multi-container orchestration (api + optional postgres profile)
├── requirements.txt            # Pinned base application dependencies
├── requirements-cv.txt         # Future CV/ML dependencies for partner handoff
├── requirements-dev.txt        # Development dependencies (pip-audit, pyyaml)
└── README.md                   # Project documentation and roadmap
```

---

## Quick Start

### Path 1: Local Python Virtualenv (SQLite)

Ideal for rapid local development, testing, and debugging.

#### 1. Windows (PowerShell)
```powershell
# 1. Clone repository and navigate to root
cd path\to\vision-api

# 2. Create virtual environment
py -m venv .venv

# 3. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Install base dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 5. Create local environment configuration
Copy-Item .env.example .env

# 6. Apply database migrations
alembic upgrade head

# 7. Start development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### 2. macOS / Linux (Bash / Zsh)
```bash
# 1. Clone repository and navigate to root
cd path/to/vision-api

# 2. Create virtual environment
python3 -m venv .venv

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install base dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 5. Create local environment configuration
cp .env.example .env

# 6. Apply database migrations
alembic upgrade head

# 7. Start development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

### Path 2: Docker Compose (SQLite)

Builds and runs the application inside an isolated Docker container with named volumes for persistent storage.

```bash
# 1. Ensure .env exists with a strong SECRET_KEY
cp .env.example .env

# 2. Build and start the api service in the background
docker compose up -d --build

# 3. View live server logs
docker compose logs -f api

# 4. Bootstrap an administrator account inside the running container
docker compose exec api python -m scripts.create_admin

# 5. Run the smoke test against the containerized API
python -m scripts.smoke_test --base-url http://127.0.0.1:8000

# 6. Stop containers
docker compose down
```

---

### Path 3: Docker Compose with PostgreSQL

Runs `vision-api` alongside a dedicated PostgreSQL 16 Alpine container using Docker Compose profiles.

```bash
# 1. Configure PostgreSQL environment variables in .env
POSTGRES_DB=vision_api
POSTGRES_USER=vision_user
POSTGRES_PASSWORD=YourSuperSecurePassword123!
DATABASE_URL=postgresql+psycopg://vision_user:YourSuperSecurePassword123!@db:5432/vision_api

# 2. Start both the API and the PostgreSQL database using the 'postgres' profile
# Setting INSTALL_POSTGRES=true ensures psycopg driver is installed in the container
INSTALL_POSTGRES=true docker compose --profile postgres up -d --build

# 3. Verify health status of both containers
docker compose --profile postgres ps

# 4. Run database migrations inside the container
docker compose exec api alembic upgrade head

# 5. Bootstrap an administrator user inside the container
docker compose exec api python -m scripts.create_admin
```

> [!NOTE]
> **Testing Status**:
> Docker is not installed on this host machine, so `docker compose build` / `docker compose up` and live PostgreSQL container execution could not be run locally. However, the `Dockerfile`, `docker-compose.yml`, shell script line endings (`\n`), and YAML syntax have all been verified through automated unit tests in `tests/test_step8_packaging.py`.

---

### Container Administration & Persistent Volumes

- **Creating an Admin Inside Docker**:
  ```bash
  docker compose exec api python -m scripts.create_admin
  ```
- **Data Persistence**:
  Application database records and uploaded media are stored in Docker named volumes:
  - `vision_api_data` (`/app/data`)
  - `vision_api_uploads` (`/app/uploads`)
  - `vision_api_postgres_data` (`/var/lib/postgresql/data` when using PostgreSQL)
- **Data Deletion Warning**:
  Running `docker compose down` stops and removes the containers but **preserves** all database records and uploaded media in the named volumes.
  Running `docker compose down -v` permanently **deletes** the named volumes, erasing all stored databases and uploaded files.

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

## CV Integration

The backend integrates with an external Computer Vision (CV) microservice that processes PPE (helmet and safety vest) compliance videos and images. The CV microservice decides compliance verdicts, tracks workers across frames, confirms multi-frame violations, and extracts worker identity. The backend validates, stores, deduplicates, notifies, and serves.

### Authentication Keys

The integration uses two distinct pre-shared service keys passed in the `X-Service-Key` header:
- `CV_SERVICE_API_KEY`: Outbound key used by the backend when calling CV microservice endpoints.
- `CV_EVENTS_API_KEY`: Inbound key used by the CV microservice when POSTing events to `/internal/api/v1/cv/events`.

Both keys must be at least 32 characters long in production (`DEBUG=false`) and must differ from each other. Generate keys via:
```powershell
py -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Event Intake & Testing Helper

The CV service posts lifecycle and detection events to the backend at `POST /internal/api/v1/cv/events`. The backend enforces idempotency using `event_id`, stores events in the `cv_events` table, and dispatches registered handlers.

You can verify the event intake pipeline using the test helper script:
```powershell
py -m scripts.send_test_event --url http://127.0.0.1:8000 --key YOUR_EVENTS_KEY
```

For the complete specification, shared data schemas, and retry semantics, see [docs/CV_INTEGRATION_CONTRACT.md](docs/CV_INTEGRATION_CONTRACT.md).

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

---

## Reliability and Security

The Vision API incorporates enterprise-grade hardening to ensure stability, confidentiality, and resilience under adversarial conditions and high traffic loads:

### 1. Consistent Error Envelope & Request ID Tracing
- **Uniform Error Shape**: Every error response (HTTP exceptions, 422 validation, 404 unknown routes, 405 method errors, 413 payload limit, 429 rate limit, 503 service busy, 504 inference timeout, and 500 unhandled exceptions) returns a standard JSON payload:
  ```json
  {"detail": "...", "request_id": "..."}
  ```
- **X-Request-ID Correlation**: The `RequestIDMiddleware` checks incoming `X-Request-ID` headers against a safe pattern (`^[a-zA-Z0-9_-]{1,64}$`), generating a UUID4 if missing or malformed. The identifier is stored in a Python `contextvars.ContextVar`, attached to every response header, embedded in all error payloads, and injected into every structured log line.
- **500 Sanitization**: Unhandled server exceptions never expose file paths, database queries, exception names, or stack traces to callers (`"An internal server error occurred."`). The full stack trace is logged server-side via `logger.exception()`.
- **422 Credential Shielding**: Pydantic input dictionaries are recursively scrubbed to ensure passwords and tokens are never echoed back in validation errors.

### 2. Startup Hardening & Production Gates
- **Production Secret Validation**: When running with `DEBUG=false`, the server strictly refuses to boot if `SECRET_KEY` is empty, equal to the insecure placeholder, or shorter than 32 characters.
- **CORS Wildcard Rejection**: When `DEBUG=false`, `ALLOWED_ORIGINS` cannot contain the wildcard `*`.
- **Documentation Toggle**: Setting `ENABLE_DOCS=false` completely disables Swagger UI (`/docs`), ReDoc (`/redoc`), and the OpenAPI schema (`/openapi.json`).

### 3. Traffic Protection & Security Headers
- **Request Body Limit**: `RequestBodyLimitMiddleware` immediately aborts any non-streaming request with `Content-Length` exceeding `MAX_REQUEST_BODY_KB` with `HTTP 413 Payload Too Large`. (Streaming detection routes maintain their own chunked counters up to `MAX_UPLOAD_MB`).
- **Security Headers**: `SecurityHeadersMiddleware` injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and applies `Cache-Control: no-store` on all `/auth/*` endpoints (avoiding CSP to ensure full Swagger UI and test bench compatibility).
- **Adaptive Rate Limiting**: `slowapi` enforces default rate limits (`DEFAULT_RATE_LIMIT=120/minute`), upload limits (`UPLOAD_RATE_LIMIT=20/minute`), refresh limits (`REFRESH_RATE_LIMIT=10/minute`), and auth limits, while exempting `/health` and `/ready` probes. When limits are exceeded, responses include standard error bodies and `Retry-After: 60` headers.

### 4. Computer Vision Inference Protection
- **Dedicated ThreadPoolExecutor**: ML detector calls run in a dedicated `ThreadPoolExecutor` initialized with `INFERENCE_WORKERS` threads.
- **Timeout Protection**: `run_inference(detector, image)` enforces `INFERENCE_TIMEOUT_SECONDS`, raising `InferenceTimeout` (`HTTP 504 Gateway Timeout`) if a detector hangs.
- **Queue Backpressure**: If active plus queued inference tasks exceed `INFERENCE_QUEUE_LIMIT`, requests are rejected immediately with `ServerBusy` (`HTTP 503 Service Unavailable`).
- **Resilient Video Processing**: Individual frame exceptions during background video processing do not crash the job. Failed frames are counted in `result.summary.frames_failed`, and jobs fail only if the failure ratio exceeds `MAX_FRAME_FAILURE_RATIO`.

### 5. Database Durability & Clean Lifecycle
- **SQLite Performance & Concurrency**: SQLite connections are initialized with `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL` (Write-Ahead Logging), `PRAGMA busy_timeout=5000`, and `PRAGMA synchronous=NORMAL`.
- **Connection Pool Pre-Ping**: Non-SQLite databases automatically enable `pool_pre_ping=True` to prune stale database connections.
- **Orphan File Cleanup**: If persisting a `Detection` or `Job` database record fails after a file has been written to disk, the file is automatically purged before the error response returns.

### 6. Health & Readiness Probes
- **GET /health**: Lightweight liveness check returning uptime, database status, and detector metadata.
- **GET /ready**: Deep readiness probe ensuring the database responds to `SELECT 1` and a detector model is loaded. Returns `HTTP 200 {"status": "ready"}` or `HTTP 503` detailing the failed component.

---

## Configuration Settings Reference

The table below describes all environment settings introduced in Step 7 alongside existing core options:

| Setting Key | Default Value | Description |
| :--- | :--- | :--- |
| `LOG_LEVEL` | `INFO` | Root logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `MAX_REQUEST_BODY_KB` | `1024` | Maximum allowable request body size in kilobytes for non-streaming routes (1024 KB = 1 MB). |
| `DEFAULT_RATE_LIMIT` | `120/minute` | Default request rate limit applied to standard API endpoints. |
| `UPLOAD_RATE_LIMIT` | `20/minute` | Rate limit applied to upload endpoints (`POST /detect/image`, `POST /detect/video`). |
| `REFRESH_RATE_LIMIT` | `10/minute` | Rate limit applied to token refresh (`POST /auth/refresh`). |
| `INFERENCE_TIMEOUT_SECONDS` | `30` | Maximum seconds permitted for an inference call before raising `InferenceTimeout` (HTTP 504). |
| `INFERENCE_WORKERS` | `2` | Number of worker threads allocated to the dedicated inference `ThreadPoolExecutor`. |
| `INFERENCE_QUEUE_LIMIT` | `8` | Maximum allowable queued + running inference calls before returning `ServerBusy` (HTTP 503). |
| `MAX_FRAME_FAILURE_RATIO` | `0.5` | Maximum ratio of frame errors tolerated before a background video job is marked failed. |
| `ENABLE_DOCS` | `true` | When `false`, disables Swagger UI (`/docs`), ReDoc (`/redoc`), and OpenAPI schema (`/openapi.json`). |
| `SECURITY_HEADERS_ENABLED` | `true` | Injects browser security headers (`nosniff`, `DENY`, `no-referrer`) and auth cache control. |
| `DEBUG` | `true` | Development mode flag; when `false`, enables strict production startup safety validations. |
| `SECRET_KEY` | *(placeholder)* | Cryptographic HMAC-SHA256 signing secret; must be at least 32 characters in production. |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Whitelisted CORS origins; wildcard `*` rejected when `DEBUG=false`. |

---

## Pre-Demo Checklist

Before presenting or deploying the application, perform this verification checklist:

1. **Start the Vision API Server**:
   ```bash
   # Windows
   py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   
   # Linux / macOS
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. **Execute Automated Smoke Test Suite**:
   Run the comprehensive smoke test against the running instance:
   ```bash
   py -m scripts.smoke_test --base-url http://127.0.0.1:8000
   ```
   Ensure all 14 checks print `[PASS]` with exit code `0`.
3. **Verify Readiness Probe**:
   Query the readiness endpoint in your browser or terminal:
   ```bash
   curl http://127.0.0.1:8000/ready
   # Expected response: {"status": "ready"} (HTTP 200)
   ```
4. **Inspect Application Logs**:
   Confirm structured JSON logs output valid `request_id` correlation IDs, that `/health` and `/ready` probes log at `DEBUG` level, and that credentials and secrets are fully redacted.

---

## Known Limitations & Future Improvements

- **Inference Thread Cancellation**: Python worker threads in a `ThreadPoolExecutor` cannot be forcibly killed upon timeout (`INFERENCE_TIMEOUT_SECONDS`). When an inference call times out, the client immediately receives an `HTTP 504 Gateway Timeout` response, but the background thread continues execution until the detector returns.
- **WebSocket Rate Limiting**: SlowAPI operates solely on HTTP ASGI scope and does not natively rate limit WebSocket frames or messages. WebSocket connections are instead throttled by `WS_MAX_CONNECTIONS_PER_USER` and message payload constraints (`WS_MAX_FRAME_KB`).
- **Reverse Proxy Client IP**: When running behind reverse proxies (Nginx, Cloudflare, Traefik, AWS ALB), Uvicorn must be started with `--proxy-headers` (e.g. `uvicorn app.main:app --proxy-headers --forwarded-allow-ips='*'`) so SlowAPI can resolve client IPs via `X-Forwarded-For`.
- **Token Revocation & Account Lockout**: Refresh tokens are stateless signed JWTs and cannot be revoked before expiration. Implementing token blocklists or account lockouts after consecutive failed attempts requires a database schema migration (targeted for a future release).
- **Chunked Request Body Limits**: Chunked HTTP requests omitting the `Content-Length` header bypass `RequestBodyLimitMiddleware` and are instead guarded by route-level chunked stream counters (`MAX_UPLOAD_MB` and `MAX_VIDEO_UPLOAD_MB`).
- **Single-Process Deployment Scope**: In-memory rate limiting counters, WebSocket active connection maps, and the inference `ThreadPoolExecutor` operate within a single process. Multi-worker or distributed deployments require an external message broker (such as Redis) and a distributed task runner (such as Celery).

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
- [x] **Step 7: Error handling and hardening**
- [x] **Step 8: Docker, CI, and partner handoff**

---

## Changelog

### Backend Patch BP1 — PPE Detection Contract, Rules Engine & Endpoints
- Schemas: Defined Pydantic v2 schemas in `app/schemas/ppe.py` for PPE items (`PpeItem`), raw worker detections (`PpeWorkerRaw`), evaluated workers (`PpeWorker`), unassigned equipment (`UnassignedItem`), pipeline information (`PpePipelineInfo`), aggregate summary statistics (`PpeSummary`), raw detector output (`PpeExtraRaw`), stored output (`PpeExtra`), and detection configuration endpoints (`DetectConfigOut`).
- Rules Engine: Implemented pure evaluation functions in `app/services/ppe_rules.py` (`parse_required_equipment`, `validate_detector_output`, `evaluate_worker`, `build_summary`, `apply_rules`) with strict validation, worker isolation, unassigned item exclusion, and precedence rules.
- Deterministic Dummy Detector: Implemented `PpeDummyDetector` in `app/services/detector/ppe_dummy.py` with 8 weighted scenarios (`all_ppe`, `no_helmet`, `no_vest`, `no_ppe`, `helmet_in_hand`, `hi_vis_not_vest`, `head_hidden`, `torso_hidden`), cheap pixel-sampling determinism, slot assignment, unassigned items, and registered under `DETECTOR_BACKEND=ppe_dummy`.
- Configuration: Added `DEFAULT_REQUIRED_EQUIPMENT=helmet,vest` and `CAMERA_NAME_MAX_LENGTH=60` in `app/core/config.py` and `.env.example`.
- API Endpoints:
  - Extended `POST /detect/image` with multipart form fields `required_equipment` and `camera_name`, with input validation (422) and PPE schema validation / rules application.
  - Added `GET /detect/config` (auth required) returning detector status, PPE capabilities, and upload constraints.
  - Added `GET /detect/{detection_id}/image` (auth required, owner or admin) returning original uploaded image with `Cache-Control: private, max-age=300` and path traversal protection.
- Documentation & Testing: Authored `docs/PPE_CONTRACT.md`, updated `docs/API_REFERENCE.md`, `docs/ARCHITECTURE.md`, `docs/PARTNER_GUIDE.md`, and added comprehensive unit and integration tests in `tests/test_ppe.py`.

### Code Review & Optimization (Phases 1–4)
- **Phase 1 (Code Hygiene & Dead Code Removal)**:
  - Fixed missing `Any` typing import in `app/api/routes/analytics.py` (resolving Ruff F821).
  - Audited and deleted 5 confirmed unused imports: `TokenError` in `app/api/deps.py`, `run_in_threadpool` in `app/api/routes/ws.py`, `Optional` in `app/models/user.py`, `ImageFile` in `app/services/image_service.py`, and `math` in `app/services/job_runner.py`.
- **Phase 2 (Query Optimization & Session Invalidation Fix)**:
  - Removed redundant `db.expire_all()` calls from route handlers in `app/api/routes/jobs.py`, `app/api/routes/alerts.py`, and `app/api/routes/analytics.py`, eliminating duplicate `SELECT ... FROM users` roundtrips on every request.
  - Aligned test client fixture in `tests/conftest.py` with production behavior so each request obtains its own isolated database session from `TestingSessionLocal()`.
  - Reduced SQL query count from 3 to 2 for `/jobs`, from 3 to 2 for `/alerts`, from 4 to 3 for `/analytics/summary`, and from 3 to 2 for `/analytics/timeseries`.
- **Phase 3 (Analytics Memory & Latency Optimization)**:
  - Optimized `GET /analytics/summary` to compute `COUNT`, `SUM(total_count)`, and `MAX(total_count)` in a single database aggregation query using portable ANSI SQL, with source types and alerts grouped at the SQL level.
  - Sourced `top_labels` by querying only `results` and `source_type` columns for rows with `total_count > 0` (capped to `ANALYTICS_MAX_ROWS`), eliminating mass deserialization of unused ORM entities.
  - Optimized `GET /analytics/timeseries` to select only scalar columns (`created_at`, `total_count`), reducing memory allocation by ~90% and cutting latency by ~2.8x over 5,000 rows.
  - Updated `truncated` semantics so numeric summary totals cover the entire date range, setting `truncated=true` when the top_labels sample (or timeseries bucket data) is capped. Added test coverage for range totals exceeding `ANALYTICS_MAX_ROWS` with role-based scoping.
- **Phase 4 (Asynchronous Concurrency & Event Loop Protection)**:
  - Offloaded synchronous image validation, decoding, and disk saving (`validate_and_save_image`) in `POST /detect/image` to Starlette's worker threadpool via `run_in_threadpool`, preventing the asyncio event loop from blocking during image uploads.
  - Verified exception mapping through threadpool (HTTP 413, 400, etc.) and guaranteed orphan-file cleanup remains active.
  - Added concurrency regression test verifying `/health` responds in <200 ms while an image upload is actively executing in the threadpool.

### Step 8 — Docker, CI, Packaging & Partner Handoff
- Created `.gitattributes` enforcing LF line endings across `*.sh`, `Dockerfile`, and `*.yml` files to prevent carriage return (`\r`) execution failures inside Linux containers.
- Created `.dockerignore` excluding `.git`, `.venv`, `__pycache__`, `.pytest_cache`, `.env` (never baked into images), `*.db`, `uploads/*`, `models_store/*`, `tests`, and `docs`.
- Built production `Dockerfile` (`python:3.12-slim`):
  - Configured `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1` with pip caching optimizations (`--no-cache-dir`).
  - Added build arguments `INSTALL_CV` (conditional `requirements-cv.txt` installation) and `INSTALL_POSTGRES` (conditional `psycopg[binary]` installation).
  - Normalizes line endings via `sed -i 's/\r$//' /app/docker/entrypoint.sh`.
  - Runs under unprivileged non-root user `appuser` (UID 1000) with ownership of `/app/data`, `/app/uploads`, `/app/models_store`, and `/app/logs`.
  - Configured native Python `urllib` health check on `GET /health` with 30s interval.
- Created container entrypoint script in `docker/entrypoint.sh`:
  - Enforces `set -e`.
  - Documents rationale for single-worker Uvicorn process (in-process `ThreadPoolExecutor` job runner and in-memory `WebSocketManager` connection tracking).
  - Applies database migrations (`alembic upgrade head`) before launching Uvicorn ASGI server with configurable `$UVICORN_ARGS`.
- Created multi-container orchestration in `docker-compose.yml`:
  - `api` service with build args, ports `"8000:8000"`, `.env` binding, health check, named persistent volumes (`app_data`, `app_uploads`), and read-only bind mount `./models_store:/app/models_store:ro`.
  - Optional `db` service (`postgres:16-alpine`) isolated under compose profile `"postgres"` with non-hardcoded password enforcement (`${POSTGRES_PASSWORD:?...}`).
- Created GitHub Actions CI in `.github/workflows/ci.yml`:
  - Automated triggers on `push` and `pull_request` to `main`.
  - Python 3.12 runner with pip caching, test-safe environment variables, pytest execution, and non-blocking `pip-audit` security scan.
- Created OpenAPI schema exporter in `scripts/export_openapi.py` generating `docs/openapi.json` without server initialization.
- Authored comprehensive frontend documentation in `docs/API_REFERENCE.md` covering all REST endpoints, standard error contracts (`request_id`), authentication lifecycle, pagination, rate limits, WebSocket protocols, and an end-to-end JavaScript client.
- Authored partner handoff guide in `docs/PARTNER_GUIDE.md` detailing YOLOv8 and OpenCV integration steps, code skeletons, performance optimizations, mocking strategies for CI, git collaboration rules, and demo-day fallback procedures.
- Added `pyyaml==6.0.3` to `requirements-dev.txt` and created comprehensive packaging test suite in `tests/test_step8_packaging.py` (all tests passing).

### Step 7 — Error Handling, Logging, Rate Limiting & Hardening
- Added 11 configuration settings in `app/core/config.py`, `.env.example`, and `.env`: `LOG_LEVEL=INFO`, `MAX_REQUEST_BODY_KB=1024`, `DEFAULT_RATE_LIMIT="120/minute"`, `UPLOAD_RATE_LIMIT="20/minute"`, `REFRESH_RATE_LIMIT="10/minute"`, `INFERENCE_TIMEOUT_SECONDS=30`, `INFERENCE_WORKERS=2`, `INFERENCE_QUEUE_LIMIT=8`, `MAX_FRAME_FAILURE_RATIO=0.5`, `ENABLE_DOCS=true`, `SECURITY_HEADERS_ENABLED=true`.
- Standardized error response contract: audited entire application so every error response (HTTPException, 422, 404, 405, 413, 429, 500, 503, 504) uses `{"detail": ..., "request_id": ...}` with no server internals, SQL, or traces exposed on 500.
- Implemented `RequestIDMiddleware`: validates incoming `X-Request-ID` against `^[a-zA-Z0-9_-]{1,64}$` (or generates UUID4), stores in `contextvars.ContextVar`, echoes in response header, injects into all logs, and embeds in all error bodies.
- Implemented `RequestLoggingMiddleware`: logs method, path (without query params), status code, duration in milliseconds, and `user_id` when known; exempts probes (`/health`, `/ready`) to `DEBUG` level; strictly omits bodies, cookies, query strings, and auth headers.
- Implemented `SensitiveDataFilter`: redacts sensitive keys (`password`, `token`, `access_token`, `refresh_token`, `authorization`, `secret`, `secret_key`, `hashed_password`) in log extras and dict messages.
- Implemented `SecurityHeadersMiddleware`: injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and applies `Cache-Control: no-store` on all `/auth/*` responses without breaking Swagger UI.
- Implemented `RequestBodyLimitMiddleware`: rejects requests with `Content-Length > MAX_REQUEST_BODY_KB` with 413, exempting streaming routes `POST /detect/image` and `POST /detect/video`.
- Added strict production startup validation: refuses startup when `DEBUG=false` if `SECRET_KEY` is empty, insecure placeholder, or < 32 characters, or if `ALLOWED_ORIGINS` contains `*`. Controlled interactive documentation via `ENABLE_DOCS`.
- Extended rate limiting: applied `DEFAULT_RATE_LIMIT` to all routes by default, `UPLOAD_RATE_LIMIT` to image and video uploads, `REFRESH_RATE_LIMIT` to token refresh, and exempted `/health` and `/ready`. Injected `Retry-After: 60` and `X-Request-ID` on 429 responses.
- Implemented inference protection in `app/services/inference.py`: shared `ThreadPoolExecutor` with `INFERENCE_WORKERS` threads; `run_inference()` with `INFERENCE_TIMEOUT_SECONDS` (mapped to 504 on upload routes) and `INFERENCE_QUEUE_LIMIT` backpressure (mapped to 503); resilient error handling on `/ws/stream` returning `{"type": "error", ...}` while maintaining socket connectivity.
- Enhanced video background job resilience: skipped failed frames during processing, stored `frames_failed` in `result.summary`, and failed jobs only when failure ratio exceeded `MAX_FRAME_FAILURE_RATIO`.
- Configured database durability: initialized SQLite connections with `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `PRAGMA synchronous=NORMAL`, and `PRAGMA foreign_keys=ON`; enabled `pool_pre_ping=True` for non-SQLite engines; implemented automatic orphan file cleanup deleting uploaded files if database row creation fails.
- Added deep readiness probe `GET /ready` verifying database connectivity (`SELECT 1`) and detector load status.
- Created `scripts/smoke_test.py` with 14 automated verification checks across health, auth, detection, jobs, history, rate limits, 404 standard errors, and WebSocket authentication without exposing secrets.
- Created `requirements-dev.txt` with `pip-audit` and conducted full vulnerability audit against `requirements.txt`.
- Added comprehensive pytest test suite in `tests/test_hardening.py` covering all hardening scenarios (99 total tests passing).
- Documented middleware architecture, Mermaid request flowchart, and error classification in `docs/ARCHITECTURE.md`.

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
