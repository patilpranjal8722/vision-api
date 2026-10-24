# vision-api 🚀

A modular, production-ready, reusable FastAPI backend template designed specifically for computer-vision hackathons and rapid ML prototyping.

The template provides an end-to-end operational backend (validation, storage, asynchronous task coordination, WebSocket feeds, and data persistence) with **zero heavy ML dependencies (no GPU, PyTorch, or OpenCV required during base development)**. A lightweight placeholder detector enables full frontend and infrastructure development until real model weights are plugged in.

---

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (High-performance async ASGI web framework)
- **ASGI Server**: [Uvicorn](https://www.uvicorn.org/) with `httptools` and `watchfiles`
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
4. **Database & Storage (`app/db/`, `app/models/`, `uploads/`)**: Relational database persistence and local/cloud storage management.

For comprehensive architectural diagrams, request lifecycles, and interface specifications, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Folder Structure

```
vision-api/
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
│   │       └── health.py       # GET /health health-check endpoint
│   ├── models/                 # Database ORM models (SQLAlchemy)
│   ├── schemas/                # Pydantic schemas and Data Transfer Objects (DTOs)
│   ├── services/               # Business logic and detector abstractions
│   └── db/                     # Database engine, session maker, and migrations
├── tests/                      # Automated test suite
│   ├── __init__.py
│   └── test_health.py          # Pytest suite validating /health endpoint
├── docs/                       # Architectural and technical documentation
│   └── ARCHITECTURE.md         # System design and detector interface details
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

# 6. Start development server
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

# 6. Start development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Verify Application

- **Interactive API Documentation (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## Running Tests

Run the automated test suite with pytest:

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
- [ ] **Step 2: Database and migrations**
- [ ] **Step 3: Authentication and roles**
- [ ] **Step 4: Detection API with DummyDetector**
- [ ] **Step 5: Video upload and background jobs**
- [ ] **Step 6: WebSocket, analytics, alerts**
- [ ] **Step 7: Error handling and hardening**
- [ ] **Step 8: Docker and partner handoff**

---

## Changelog

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
