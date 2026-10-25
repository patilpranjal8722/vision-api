"""Application middleware components for request ID tracing, security headers, logging, and body limits."""

import re
import time
import uuid
from typing import Any, Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.context import get_request_id, reset_request_id, set_request_id
from app.core.logging import get_logger

logger = get_logger("vision_api.access")

SAFE_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Enforces, extracts, or generates a safe UUID request ID for every request."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        incoming_id = request.headers.get("x-request-id")
        if incoming_id and SAFE_REQUEST_ID_REGEX.match(incoming_id):
            req_id = incoming_id
        else:
            req_id = str(uuid.uuid4())

        token = set_request_id(req_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            reset_request_id(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects essential security headers into responses."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        response = await call_next(request)
        settings = get_settings()

        if settings.SECURITY_HEADERS_ENABLED:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            # Prevent caching sensitive credential responses on authentication endpoints
            if request.url.path.startswith("/auth"):
                response.headers["Cache-Control"] = "no-store"
            # NOTE: Content-Security-Policy (CSP) is intentionally omitted to avoid breaking
            # Swagger UI (/docs) inline styles and the developer testbench (/ws-test).

        return response


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """Guards non-upload endpoints against oversized request payloads."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        settings = get_settings()

        # Enforce body limits on write methods, excluding endpoints with dedicated streaming limits
        if request.method in ("POST", "PUT", "PATCH") and request.url.path not in (
            "/detect/image",
            "/detect/video",
        ):
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    length = int(content_length)
                    max_bytes = settings.MAX_REQUEST_BODY_KB * 1024
                    if length > max_bytes:
                        req_id = get_request_id() or str(uuid.uuid4())
                        return JSONResponse(
                            status_code=413,
                            content={
                                "detail": f"Request body exceeds maximum allowed limit of {settings.MAX_REQUEST_BODY_KB} KB",
                                "request_id": req_id,
                            },
                            headers={"X-Request-ID": req_id},
                        )
                except ValueError:
                    pass

        # NOTE: Chunked transfer-encoding requests without a Content-Length header
        # bypass this middleware check but are safely bounded and enforced by downstream
        # route-level streaming limits in image and video processing services.
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming request method, path, status, duration, and user ID without logging bodies or credentials."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        path = request.url.path
        method = request.method
        status_code = response.status_code
        user_id = getattr(request.state, "user_id", None)

        log_payload = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }
        if user_id is not None:
            log_payload["user_id"] = user_id

        # Log liveness and readiness probes at DEBUG level to avoid log pollution
        if path in ("/health", "/ready"):
            logger.debug(
                f"{method} {path} - {status_code} ({duration_ms}ms)",
                extra=log_payload,
            )
        else:
            logger.info(
                f"{method} {path} - {status_code} ({duration_ms}ms)",
                extra=log_payload,
            )

        return response
