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

### Known Limitations

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
- [ ] **Step 4: Detection API with DummyDetector**
- [ ] **Step 5: Video upload and background jobs**
- [ ] **Step 6: WebSocket, analytics, alerts**
- [ ] **Step 7: Error handling and hardening**
- [ ] **Step 8: Docker and partner handoff**

---

## Changelog

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
