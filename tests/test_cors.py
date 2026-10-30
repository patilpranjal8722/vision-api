"""Tests for CORS preflight headers and allowed frontend origins."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def cors_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Create a TestClient with deterministic CORS settings independent of local environment files."""
    settings = Settings(
        ALLOWED_ORIGINS=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:5173",
        ],
        SECRET_KEY="test-secret-key-at-least-32-chars-long",
    )
    app = create_app(settings=settings)
    return TestClient(app)


def test_cors_preflight_127_0_0_1_5173(cors_client: TestClient) -> None:
    """A preflight OPTIONS request from http://127.0.0.1:5173 returns 200 and matching allow-origin header."""
    response = cors_client.options(
        "/detect/image",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_cors_preflight_localhost_5173(cors_client: TestClient) -> None:
    """A preflight OPTIONS request from http://localhost:5173 returns 200 and matching allow-origin header."""
    response = cors_client.options(
        "/detect/image",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_preflight_disallowed_origin(cors_client: TestClient) -> None:
    """A preflight OPTIONS request from an unauthorized origin does not receive an allow-origin header."""
    response = cors_client.options(
        "/detect/image",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_default_config_includes_vite_port_5173() -> None:
    """Verify that default settings field definition includes port 5173 origins."""
    default_origins = Settings.model_fields["ALLOWED_ORIGINS"].default
    assert "http://localhost:5173" in default_origins
    assert "http://127.0.0.1:5173" in default_origins
