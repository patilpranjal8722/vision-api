"""Pytest fixtures and temporary database setup.

Provides an isolated in-memory SQLite database for tests, ensuring the
development/production database files are never touched during testing.
"""

from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pathlib import Path
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


@pytest.fixture(autouse=True)
def setup_test_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate uploaded files to a temporary folder during tests."""
    temp_dir = tmp_path / "test_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(temp_dir))
    return temp_dir

# Use an in-memory SQLite database with StaticPool so all connections share the same memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Enforce foreign key constraints on SQLite test engine
@event.listens_for(engine_test, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine_test,
)


@pytest.fixture(autouse=True)
def setup_test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure test defaults: inline runner, 0ms frame delay, in-memory SessionLocal."""
    settings = get_settings()
    monkeypatch.setattr(settings, "JOB_RUNNER_INLINE", True)
    monkeypatch.setattr(settings, "DUMMY_FRAME_DELAY_MS", 0)
    monkeypatch.setattr(settings, "DETECTOR_BACKEND", "dummy")
    monkeypatch.setattr("app.db.session.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.services.job_runner.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.api.routes.ws.SessionLocal", TestingSessionLocal)


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Create all tables before each test and drop them afterward."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(autouse=True)
def disable_rate_limiting_by_default() -> Generator[None, None, None]:
    """Disable slowapi rate limiting for unit tests unless explicitly enabled in a test."""
    original_state = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original_state


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a transactional test database session."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with overridden database session dependency."""
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
