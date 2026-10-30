"""Main entrypoint for the vision-api application.

This module sets up the FastAPI application instance using the application factory
pattern (`create_app()`). For beginners learning FastAPI, key concepts are explained
throughout this file:

1. Application Factory (`create_app()`):
   A function that constructs and configures a FastAPI app instance. Using a factory
   pattern makes it easy to create multiple instances with different configurations,
   such as during automated testing or running in production.

2. Lifespan Events (`lifespan()`):
   An async context manager executed once when the server starts up and shuts down.
   Code before the `yield` runs on startup (e.g., initializing database connections,
   loading model configurations, starting workers). Code after the `yield` runs on
   shutdown (e.g., closing connections, freeing resources).

3. Middleware Onion Architecture:
   Middlewares wrap incoming requests and outgoing responses in a clean layered onion:
   - RequestIDMiddleware: Extracts, generates, and propagates request IDs.
   - SecurityHeadersMiddleware: Adds nosniff, DENY, no-referrer, and Cache-Control headers.
   - RequestBodyLimitMiddleware: Guards write endpoints against oversized payloads.
   - RequestLoggingMiddleware: Logs method, path, status, and duration (DEBUG for probes).
   - CORSMiddleware: Handles Cross-Origin Resource Sharing.

4. Consistent Error Responses:
   Every error (HTTPException, 422, 429, 413, 500) returns a uniform JSON structure:
   `{"detail": ..., "request_id": ...}` with the `X-Request-ID` header.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator
import uuid
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes.alerts import router as alerts_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.cv_events import router as cv_events_router
from app.api.routes.detect import router as detect_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.test_page import router as test_page_router
from app.api.routes.users import router as users_router
from app.api.routes.ws import router as ws_router
from app.core.config import INSECURE_SECRET_PLACEHOLDER, Settings, get_settings
from app.core.context import get_request_id
from app.core.limiter import limiter
from app.core.logging import get_logger, setup_logging
from app.core.middleware import (
    RequestBodyLimitMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from app.services.detector import get_detector
from app.services.inference import inference_manager
from app.services.job_runner import JobRunner, reconcile_stale_jobs
from app.services.ws_manager import ws_manager

logger = get_logger("vision_api.main")


def validate_startup_settings(settings: Settings) -> None:
    """Validate critical security settings at startup.

    Refuses to start in production (DEBUG=false) if secret key is insecure or wildcard CORS is enabled.
    """
    if not settings.DEBUG:
        if (
            not settings.SECRET_KEY
            or settings.SECRET_KEY == INSECURE_SECRET_PLACEHOLDER
            or len(settings.SECRET_KEY) < 32
        ):
            raise RuntimeError(
                "Production startup failed: SECRET_KEY must be set, must not use default placeholder, "
                "and must be at least 32 characters long when DEBUG=false."
            )
        if "*" in settings.ALLOWED_ORIGINS:
            raise RuntimeError(
                "Production startup failed: ALLOWED_ORIGINS must not contain wildcard '*' when DEBUG=false."
            )
        if not settings.CV_SERVICE_API_KEY or len(settings.CV_SERVICE_API_KEY) < 32:
            raise RuntimeError(
                "Production startup failed: CV_SERVICE_API_KEY must be set and at least 32 characters long when DEBUG=false."
            )
        if not settings.CV_EVENTS_API_KEY or len(settings.CV_EVENTS_API_KEY) < 32:
            raise RuntimeError(
                "Production startup failed: CV_EVENTS_API_KEY must be set and at least 32 characters long when DEBUG=false."
            )
        if settings.CV_SERVICE_API_KEY == settings.CV_EVENTS_API_KEY:
            raise RuntimeError(
                "Production startup failed: CV_SERVICE_API_KEY and CV_EVENTS_API_KEY must differ from each other."
            )
    else:
        if (
            not settings.SECRET_KEY
            or settings.SECRET_KEY == INSECURE_SECRET_PLACEHOLDER
            or len(settings.SECRET_KEY) < 32
        ):
            logger.warning(
                "SECURITY WARNING: SECRET_KEY is empty, insecure, or shorter than 32 characters! "
                "Never use default or weak keys in production. "
                "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        if not settings.CV_SERVICE_API_KEY:
            logger.warning("CV_SERVICE_API_KEY is empty. Outbound CV microservice requests will be unauthenticated.")
        if not settings.CV_EVENTS_API_KEY:
            logger.warning("CV_EVENTS_API_KEY is empty. Inbound calls to /internal/api/v1/cv/events will be refused with 401.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager managing application startup and shutdown events."""
    settings: Settings = get_settings()

    # --- Startup phase ---
    validate_startup_settings(settings)
    setup_logging(log_level_str=settings.LOG_LEVEL, debug=settings.DEBUG)

    # Initialize shared inference threadpool executor
    try:
        inference_manager.init_executor(settings.INFERENCE_WORKERS)
    except Exception as exc:
        logger.error(f"Failed to initialize inference manager: {exc}", exc_info=True)

    # Store active event loop for thread-safe cross-thread WebSocket pushes
    try:
        loop = asyncio.get_running_loop()
        ws_manager.set_event_loop(loop)
    except Exception as exc:
        logger.warning(f"Could not store running event loop in ws_manager: {exc}")

    # Reconcile stale jobs from any previous server session
    try:
        reconcile_stale_jobs()
    except Exception as exc:
        logger.error(f"Failed to reconcile stale jobs at startup: {exc}", exc_info=True)

    # Detector initialization (load model once at startup)
    try:
        detector = get_detector(settings)
        detector.load()
        app.state.detector = detector
        logger.info(
            "Detector loaded successfully",
            extra={
                "detector_name": detector.name,
                "is_placeholder": detector.is_placeholder,
            },
        )
    except Exception as exc:
        logger.error(
            f"Failed to load detector: {exc}",
            exc_info=True,
            extra={"detector_backend": settings.DETECTOR_BACKEND},
        )
        app.state.detector = None

    # Job runner initialization (ThreadPoolExecutor)
    try:
        job_runner = JobRunner(app, settings)
        app.state.job_runner = job_runner
        logger.info(
            "Job runner initialized successfully",
            extra={
                "max_concurrent_jobs": settings.MAX_CONCURRENT_JOBS,
                "job_runner_inline": settings.JOB_RUNNER_INLINE,
            },
        )
    except Exception as exc:
        logger.error(f"Failed to initialize job runner: {exc}", exc_info=True)
        app.state.job_runner = None

    logger.info(
        "Application starting up",
        extra={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "detector_backend": settings.DETECTOR_BACKEND,
            "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
        },
    )

    yield

    # --- Shutdown phase ---
    job_runner = getattr(app.state, "job_runner", None)
    if job_runner is not None:
        try:
            job_runner.shutdown(wait=False)
            logger.info("Job runner shut down successfully")
        except Exception as exc:
            logger.error(f"Error shutting down job runner: {exc}", exc_info=True)

    detector = getattr(app.state, "detector", None)
    if detector is not None:
        try:
            detector.close()
            logger.info("Detector closed successfully")
        except Exception as exc:
            logger.error(f"Error closing detector on shutdown: {exc}", exc_info=True)

    inference_manager.shutdown(wait=False)
    logger.info("Application shutting down gracefully")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Return project standard error JSON for HTTPExceptions including 404 and 405."""
    req_id = get_request_id() or str(uuid.uuid4())
    headers = dict(exc.headers or {})
    headers["X-Request-ID"] = req_id
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": req_id},
        headers=headers,
    )


async def rate_limit_custom_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return project standard error JSON with Retry-After header when rate limits are exceeded."""
    req_id = get_request_id() or str(uuid.uuid4())
    response = JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}", "request_id": req_id},
        headers={"X-Request-ID": req_id},
    )
    if hasattr(request.app.state, "limiter"):
        response = request.app.state.limiter._inject_headers(
            response, getattr(request.state, "view_rate_limit", None)
        )
    if "Retry-After" not in response.headers:
        response.headers["Retry-After"] = "60"
    response.headers["X-Request-ID"] = req_id
    return response


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return standard 422 response with request_id while stripping sensitive credentials."""
    req_id = get_request_id() or str(uuid.uuid4())
    raw_errors = exc.errors()
    sanitized_errors = []
    for err in raw_errors:
        err_dict = dict(err)
        loc = [str(x).lower() for x in err_dict.get("loc", ())]
        if any("password" in part or "token" in part for part in loc):
            err_dict.pop("input", None)
        elif "input" in err_dict:
            from app.core.logging import redact_sensitive_data
            err_dict["input"] = redact_sensitive_data(err_dict["input"])
        sanitized_errors.append(err_dict)

    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(sanitized_errors), "request_id": req_id},
        headers={"X-Request-ID": req_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled server errors, log tracebacks server-side, and return sanitized 500 JSON."""
    req_id = get_request_id() or str(uuid.uuid4())
    logger.exception(
        f"Unhandled exception while processing {request.method} {request.url.path}: {exc}",
        extra={"request_id": req_id},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": req_id},
        headers={"X-Request-ID": req_id},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a new instance of the FastAPI application."""
    if settings is None:
        settings = get_settings()

    # Refuse startup in production under unsafe configurations
    validate_startup_settings(settings)

    # Determine OpenAPI documentation endpoints based on ENABLE_DOCS setting
    docs_url = "/docs" if settings.ENABLE_DOCS else None
    redoc_url = "/redoc" if settings.ENABLE_DOCS else None
    openapi_url = "/openapi.json" if settings.ENABLE_DOCS else None

    # Initialize the FastAPI app instance with metadata for OpenAPI documentation
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Reusable FastAPI backend template for computer-vision hackathons.",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # Attach slowapi rate limiter to app state and register uniform exception handlers
    application.state.limiter = limiter
    application.state.detector = None
    application.state.job_runner = None

    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RateLimitExceeded, rate_limit_custom_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)

    # Add middlewares (executed in reverse order: RequestID -> SecurityHeaders -> BodyLimit -> Logging -> CORS)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(RequestBodyLimitMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestIDMiddleware)

    # Register API route modules
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(detect_router)
    application.include_router(jobs_router)
    application.include_router(alerts_router)
    application.include_router(analytics_router)
    application.include_router(ws_router)
    application.include_router(test_page_router)
    application.include_router(cv_events_router)
    return application


# Global application instance for ASGI servers (e.g., `uvicorn app.main:app`)
app = create_app()
