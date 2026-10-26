# ==============================================================================
# vision-api - Multi-Stage / Production Dockerfile
# ==============================================================================
# Base image: Official lightweight Python 3.12 Debian slim image.
# Using 'slim' keeps the final image minimal, fast to pull, and secure by
# omitting unnecessary build compilers and debug packages.
# ==============================================================================
FROM python:3.12-slim

# ------------------------------------------------------------------------------
# 1. Environment Configuration
# ------------------------------------------------------------------------------
# PYTHONDONTWRITEBYTECODE=1: Prevents Python from writing .pyc files to disk
# (reduces disk I/O and keeps container layers clean).
# PYTHONUNBUFFERED=1: Forces stdout and stderr streams to be unbuffered so that
# logs appear in real-time in `docker logs` without buffering delays.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the primary working directory inside the container
WORKDIR /app

# ------------------------------------------------------------------------------
# 2. Dependency Installation
# ------------------------------------------------------------------------------
# Build arguments for conditional dependencies:
# - INSTALL_CV: If 'true', also installs requirements-cv.txt (YOLO, OpenCV, PyTorch).
# - INSTALL_POSTGRES: If 'true', also installs psycopg[binary] for PostgreSQL support.
# Defaults are 'false' to keep the image lightweight and fast for development.
ARG INSTALL_CV=false
ARG INSTALL_POSTGRES=false

# Copy dependency definition files first to leverage Docker layer caching.
# If source code changes in app/, Docker can reuse this cached dependency layer.
COPY requirements.txt requirements-cv.txt /app/

# Install dependencies using pip with --no-cache-dir to avoid bloating the image.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_CV" = "true" ]; then \
        echo "Installing CV/ML dependencies from requirements-cv.txt..." && \
        pip install --no-cache-dir -r requirements-cv.txt; \
    fi && \
    if [ "$INSTALL_POSTGRES" = "true" ]; then \
        echo "Installing PostgreSQL psycopg driver..." && \
        pip install --no-cache-dir "psycopg[binary]>=3.1.0"; \
    fi

# ------------------------------------------------------------------------------
# 3. Application Source & Directories Setup
# ------------------------------------------------------------------------------
# Copy the application packages, database migration scripts, and utilities.
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini
COPY scripts/ /app/scripts/
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

# Normalize line endings and set executable permission on the entrypoint script.
# Windows editors may introduce CRLF (\r\n) line endings which break Linux shells.
RUN sed -i 's/\r$//' /app/docker/entrypoint.sh && \
    chmod +x /app/docker/entrypoint.sh

# ------------------------------------------------------------------------------
# 4. Security & Non-Root User Setup
# ------------------------------------------------------------------------------
# Running as non-root mitigates container escape vulnerabilities.
# Create a dedicated system user 'appuser' with UID 1000.
# Create required runtime directories (/app/data, /app/uploads, /app/models_store, /app/logs)
# and assign ownership to appuser.
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    mkdir -p /app/data /app/uploads /app/models_store /app/logs && \
    chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# ------------------------------------------------------------------------------
# 5. Network Port & Health Check
# ------------------------------------------------------------------------------
# Inform Docker that the container listens on port 8000 at runtime
EXPOSE 8000

# Periodic health check calling GET /health using Python's built-in urllib.
# This avoids needing 'curl' or 'wget' installed in the slim container image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').getcode() == 200 else 1)"

# ------------------------------------------------------------------------------
# 6. Container Entrypoint
# ------------------------------------------------------------------------------
# Use entrypoint.sh to run migrations and launch Uvicorn with a single worker.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
