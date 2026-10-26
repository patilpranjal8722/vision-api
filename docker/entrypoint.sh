#!/bin/sh
set -e

# ==============================================================================
# vision-api Container Entrypoint Script
# ==============================================================================
# Why exactly ONE Uvicorn worker process?
# ----------------------------------------
# 1. In-process Job Runner (ThreadPoolExecutor): Video background jobs submitted
#    via POST /detect/video are managed in-memory on app.state.job_runner. If
#    multiple worker processes were used, status checks (GET /jobs/{id}) routed
#    to a different process would lack coordination with the running thread.
# 2. In-process WebSocket Manager (WebSocketManager): Active WebSocket connections
#    for /ws/alerts and /ws/stream are tracked in-memory. Cross-thread alerts and
#    broadcasts are pushed within the ASGI event loop of a single process. Running
#    multiple workers without an external message broker (like Redis Pub/Sub)
#    would isolate clients into disjoint worker silos.
#
# Horizontal scaling to multi-worker or multi-container architectures requires
# backing WebSocket broadcasts with Redis Pub/Sub and background jobs with Celery/RQ.
# ==============================================================================

echo "==> Running database migrations (alembic upgrade head)..."
alembic upgrade head

echo "==> Starting Uvicorn ASGI server on 0.0.0.0:8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 $UVICORN_ARGS
