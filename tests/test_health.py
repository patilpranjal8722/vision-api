"""Tests for the /health endpoint using FastAPI TestClient."""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.config import get_settings


@pytest.fixture
def client() -> TestClient:
    """Create a TestClient fixture with the application instance."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_check_returns_200_and_expected_keys(client: TestClient) -> None:
    """Test that GET /health returns HTTP 200 and all expected payload keys."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    expected_keys = {"status", "app_name", "version", "timestamp", "model_loaded"}
    assert expected_keys.issubset(data.keys()), f"Missing keys in response: {expected_keys - set(data.keys())}"

    # Verify key values
    settings = get_settings()
    assert data["status"] == "ok"
    assert data["app_name"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION
    assert data["model_loaded"] is False

    # Verify timestamp is a valid ISO 8601 string
    parsed_timestamp = datetime.fromisoformat(data["timestamp"])
    assert parsed_timestamp is not None
