# vision-api 🚀

A modular, production-ready, reusable FastAPI backend template designed specifically for computer-vision hackathons and rapid ML prototyping.

The template provides an end-to-end operational backend (validation, storage, asynchronous task coordination, WebSocket feeds, and data persistence) with **zero heavy ML dependencies (no GPU, PyTorch, or OpenCV required during base development)**. A lightweight placeholder detector enables full frontend and infrastructure development until real model weights are plugged in.

---

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (High-performance async ASGI web framework)
- **ASGI Server**: [Uvicorn](https://www.uvicorn.org/) with `httptools` and `watchfiles`
- **Database & ORM**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (`DeclarativeBase`, `Mapped`, `mapped_column`)
- **Database Migrations**: [Alembic](https://alembic.sqlalchemy.org/) (with SQLite batch-mode support)
- **Configuration & Validation**: [Pydantic v2](https://docs.pydantic.dev/) and [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **File Uploads**: `python-multipart`
- **Testing**: [pytest](https://docs.pytest.org/) and [HTTPX](https://www.python-httpx.org/) (FastAPI `TestClient`)
- **Logging**: Structured JSON logging via standard library `logging`

---

## Architecture Summary

The project is built on a clean layered architecture following the Dependency Inversion Principle:

1. **API Routes (`app/api/routes/`)**: Handles HTTP requests, parameter validation, and status codes.
2. **Services (`app/services/`)**: Orchestrates business logic, file storage, and detector execution.
3. **Detector Abstraction (`app/services/`)**: Standard interface (`BaseDetector`) allowing seamless switching between `DummyDetector` (mock data, no GPU) and `YoloDetector` without altering routes or services.
4. **Database & Storage (`app/db/`, `app/models/`, `uploads/`)**: Relational database persistence (User, Job, Detection, Alert) and local/cloud storage management.

For comprehensive architectural diagrams, request lifecycles, and database ER diagrams, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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
│   ├── main.py                 # Application factory (create_app), lifespan, CORS, and routes
│   ├── core/                   # Application-wide core modules
│   │   ├── __init__.py
│   │   ├── config.py           # Pydantic Settings class loading from .env
│   │   └── logging.py          # Structured JSON logging setup (no print statements)
│   ├── api/                    # API routing layer
│   │   ├── __init__.py
│   │   └── routes/             # Route handlers
│   │       ├── __init__.py
│   │       └── health.py       # GET /health health-check & DB connectivity endpoint
│   ├── models/                 # Database ORM models (SQLAlchemy 2.0)
│   │   ├── __init__.py         # Exports Base, User, Job, Detection, Alert
│   │   ├── user.py             # User accounts, hashed passwords, roles
│   │   ├── job.py              # Asynchronous image/video processing jobs
│   │   ├── detection.py        # Object detection results & bounding boxes
│   │   └── alert.py            # Event alerts and notifications
│   ├── schemas/                # Pydantic schemas and Data Transfer Objects (DTOs)
│   ├── services/               # Business logic and detector abstractions
│   └── db/                     # Database engine, session maker, and Base
│       ├── __init__.py
│       ├── base.py             # DeclarativeBase definition
│       └── session.py          # Engine, SQLite PRAGMA hook, and get_db() dependency
├── tests/                      # Automated test suite
│   ├── __init__.py
│   ├── conftest.py             # Isolated in-memory SQLite fixture & TestClient
│   ├── test_health.py          # Pytest suite validating /health endpoint & degraded state
│   └── test_models.py          # Pytest suite verifying ORM models & constraints
├── docs/                       # Architectural and technical documentation
│   └── ARCHITECTURE.md         # System design, request flow, and ER diagram
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
- [ ] **Step 3: Authentication and roles**
- [ ] **Step 4: Detection API with DummyDetector**
- [ ] **Step 5: Video upload and background jobs**
- [ ] **Step 6: WebSocket, analytics, alerts**
- [ ] **Step 7: Error handling and hardening**
- [ ] **Step 8: Docker and partner handoff**

---

## Changelog

### Step 2 — Database, Models & Migrations
- Added `sqlalchemy==2.1.6` and `alembic==1.20.1` to `requirements.txt` with exact pinned versions.
- Built `app/db/base.py` (`Base = DeclarativeBase`) and `app/db/session.py` with SQLite PRAGMA foreign keys enforcement and `get_db()` dependency generator.
- Implemented four SQLAlchemy 2.0 models with UTC timezone-aware datetimes and portable JSON fields:
  - `User`: Accounts with role-based checks, unique indexed email/username, and password hash.
  - `Job`: Asynchronous task state machine with UUID primary key, progress percentage, and JSON results.
  - `Detection`: Detection instances storing bounding boxes, labels, counts, and metadata.
  - `Alert`: Priority notifications linked to users and detections with read status.
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
