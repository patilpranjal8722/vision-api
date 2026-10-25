"""Tests for the /health endpoint using FastAPI TestClient."""

from datetime import datetime
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app


def test_health_check_returns_200_and_database_ok(client: TestClient) -> None:
    """Test that GET /health returns HTTP 200, all expected keys, and database 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    expected_keys = {
        "status",
        "app_name",
        "version",
        "timestamp",
        "detector",
        "model_loaded",
        "detector_is_placeholder",
        "database",
        "active_jobs",
        "ws_connections",
    }
    assert expected_keys.issubset(data.keys()), f"Missing keys in response: {expected_keys - set(data.keys())}"

    # Verify key values
    settings = get_settings()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["app_name"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION
    assert data["detector"] == "dummy"
    assert data["model_loaded"] is True
    assert data["detector_is_placeholder"] is True
    assert data["active_jobs"] == 0
    assert data["ws_connections"] == 0

    # Verify timestamp is a valid ISO 8601 string
    parsed_timestamp = datetime.fromisoformat(data["timestamp"])
    assert parsed_timestamp is not None


def test_health_check_degraded_when_database_fails() -> None:
    """Test that /health returns status 'degraded' and database 'error' without crashing when DB fails."""
    app = create_app()

    # Mock failing database session
    mock_db = MagicMock()
    mock_db.execute.side_effect = RuntimeError("Database connection timed out")

    def override_broken_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_broken_db

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "error"
        assert data["model_loaded"] is True
        assert data["detector"] == "dummy"

    app.dependency_overrides.clear()


def test_health_check_degraded_when_detector_fails_to_load() -> None:
    """Test that /health returns status 'degraded' when detector is None or failed to load."""
    app = create_app()

    with TestClient(app) as client:
        # Simulate failed detector load on app state
        app.state.detector = None
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "degraded"
        assert data["detector"] is None
        assert data["model_loaded"] is False
        assert data["detector_is_placeholder"] is False
