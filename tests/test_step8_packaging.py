"""Automated test suite verifying Step 8 packaging, Docker configuration, CI, and OpenAPI export."""

import json
from pathlib import Path
import yaml
import pytest

from scripts.export_openapi import export_openapi_schema


def test_entrypoint_script_no_carriage_returns():
    """Verify docker/entrypoint.sh contains strictly LF line endings (no \\r characters)."""
    entrypoint_path = Path("docker/entrypoint.sh")
    assert entrypoint_path.exists(), "docker/entrypoint.sh must exist"

    content_bytes = entrypoint_path.read_bytes()
    assert b"\r" not in content_bytes, "docker/entrypoint.sh contains Windows carriage return (\\r) characters"
    assert b"alembic upgrade head" in content_bytes, "docker/entrypoint.sh must run alembic upgrade head"
    assert b"uvicorn app.main:app" in content_bytes, "docker/entrypoint.sh must run uvicorn"
    assert b"set -e" in content_bytes, "docker/entrypoint.sh must enable set -e"


def test_dockerignore_exclusions():
    """Verify .dockerignore excludes sensitive secrets, venv, git, and database files."""
    dockerignore_path = Path(".dockerignore")
    assert dockerignore_path.exists(), ".dockerignore must exist"

    lines = [
        line.strip()
        for line in dockerignore_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    # Verify required exclusions
    assert ".env" in lines, ".dockerignore must exclude .env secrets"
    assert ".git" in lines, ".dockerignore must exclude .git directory"
    assert ".venv" in lines, ".dockerignore must exclude .venv virtual environment"
    assert any("*.db" in l for l in lines), ".dockerignore must exclude *.db database files"


def test_docker_compose_configuration():
    """Verify docker-compose.yml parses as valid YAML and adheres to service constraints."""
    compose_path = Path("docker-compose.yml")
    assert compose_path.exists(), "docker-compose.yml must exist"

    compose_data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert isinstance(compose_data, dict), "docker-compose.yml must parse as a dictionary"

    services = compose_data.get("services", {})
    assert "api" in services, "docker-compose.yml must define 'api' service"

    # API service verification
    api_service = services["api"]
    assert "healthcheck" in api_service, "api service must define a healthcheck"
    assert "8000:8000" in api_service.get("ports", []), "api service must expose port 8000:8000"

    volumes = api_service.get("volumes", [])
    assert any("models_store" in v and ":ro" in v for v in volumes), (
        "api service must mount models_store as read-only (:ro)"
    )

    # Optional DB service verification
    assert "db" in services, "docker-compose.yml must define optional 'db' service"
    db_service = services["db"]
    assert "postgres" in db_service.get("profiles", []), "db service must be under the 'postgres' compose profile"
    assert "healthcheck" in db_service, "db service must define a healthcheck"

    # Verify no hardcoded password exists in compose file
    db_env = db_service.get("environment", {})
    if isinstance(db_env, dict):
        pw_spec = str(db_env.get("POSTGRES_PASSWORD", ""))
    elif isinstance(db_env, list):
        pw_spec = "".join(str(item) for item in db_env if "POSTGRES_PASSWORD" in str(item))
    else:
        pw_spec = ""

    assert "${POSTGRES_PASSWORD:?" in pw_spec, (
        "POSTGRES_PASSWORD must use the ${POSTGRES_PASSWORD:?message} syntax and must NOT be hardcoded"
    )


def test_ci_workflow_parses_and_runs_pytest():
    """Verify .github/workflows/ci.yml parses as YAML and executes pytest."""
    ci_path = Path(".github/workflows/ci.yml")
    assert ci_path.exists(), ".github/workflows/ci.yml must exist"

    ci_data = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
    assert isinstance(ci_data, dict), ".github/workflows/ci.yml must parse as a dictionary"

    # Verify triggers ('on' or boolean True in YAML 1.1)
    triggers = ci_data.get("on") or ci_data.get(True) or {}
    assert "push" in triggers, "CI must trigger on push"
    assert "pull_request" in triggers, "CI must trigger on pull_request"

    # Verify steps execute pytest and pip-audit
    jobs = ci_data.get("jobs", {})
    assert "test" in jobs, "CI must define a 'test' job"
    steps = jobs["test"].get("steps", [])

    pytest_step_found = False
    audit_step_found = False
    for step in steps:
        run_cmd = step.get("run", "")
        if "pytest" in run_cmd:
            pytest_step_found = True
        if "pip-audit" in run_cmd:
            audit_step_found = True
            assert step.get("continue-on-error") is True, "pip-audit step must continue on error (non-blocking)"

    assert pytest_step_found, "CI workflow must run pytest"
    assert audit_step_found, "CI workflow must run pip-audit"


def test_openapi_export_and_required_routes(tmp_path):
    """Verify OpenAPI export generates valid JSON containing all specified core endpoints."""
    out_file = tmp_path / "openapi_test.json"
    dest = export_openapi_schema(output_path=out_file)

    assert dest.exists(), "Exported OpenAPI schema file must exist"
    with open(dest, "r", encoding="utf-8") as f:
        schema = json.load(f)

    paths = schema.get("paths", {})
    required_routes = [
        "/auth/login",
        "/detect/image",
        "/detect/video",
        "/jobs/{job_id}",
        "/alerts",
        "/analytics/summary",
        "/health",
        "/ready",
    ]

    for route in required_routes:
        assert route in paths, f"OpenAPI schema must contain route path '{route}'"


def test_dockerfile_contents():
    """Verify Dockerfile specifies python:3.12-slim, non-root user, and healthcheck."""
    dockerfile_path = Path("Dockerfile")
    assert dockerfile_path.exists(), "Dockerfile must exist"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in content, "Dockerfile must use python:3.12-slim"
    assert "PYTHONDONTWRITEBYTECODE=1" in content, "Dockerfile must set PYTHONDONTWRITEBYTECODE=1"
    assert "PYTHONUNBUFFERED=1" in content, "Dockerfile must set PYTHONUNBUFFERED=1"
    assert "INSTALL_CV" in content, "Dockerfile must support INSTALL_CV build arg"
    assert "INSTALL_POSTGRES" in content, "Dockerfile must support INSTALL_POSTGRES build arg"
    assert "USER appuser" in content, "Dockerfile must run as non-root user appuser"
    assert "HEALTHCHECK" in content, "Dockerfile must configure HEALTHCHECK"
    assert "urllib.request" in content, "Dockerfile healthcheck should use urllib"


def test_gitattributes_contents():
    """Verify .gitattributes enforces LF on scripts, Dockerfile, and YAML."""
    gitattributes_path = Path(".gitattributes")
    assert gitattributes_path.exists(), ".gitattributes must exist"

    content = gitattributes_path.read_text(encoding="utf-8")
    assert "* text=auto" in content
    assert "*.sh text eol=lf" in content
    assert "Dockerfile text eol=lf" in content
    assert "*.yml text eol=lf" in content
