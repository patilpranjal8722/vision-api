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

3. Middleware (`CORSMiddleware`):
   Middleware intercepts incoming HTTP requests before they reach route handlers,
   and outgoing responses before they are returned to clients.
   CORS (Cross-Origin Resource Sharing) headers allow or restrict frontend web apps
   (such as React, Vue, or Next.js running on different ports or domains) from calling
   this API.

4. Routers (`app.include_router()`):
   FastAPI uses APIRouter instances to modularize routes across multiple files
   instead of writing every endpoint in a single massive file.

5. Rate Limiting (`slowapi`):
   Limits repetitive requests (such as brute-force password guessing) per client IP address.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.users import router as users_router
from app.core.config import INSECURE_SECRET_PLACEHOLDER, Settings, get_settings
from app.core.limiter import limiter
from app.core.logging import get_logger, setup_logging

logger = get_logger("vision_api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager managing application startup and shutdown events."""
    settings: Settings = get_settings()

    # --- Startup phase ---
    setup_logging(debug=settings.DEBUG)

    # Security check: verify SECRET_KEY is not empty or using the default placeholder
    if not settings.SECRET_KEY or settings.SECRET_KEY == INSECURE_SECRET_PLACEHOLDER:
        logger.warning(
            "SECURITY WARNING: SECRET_KEY is empty or using an insecure placeholder! "
            "Never use default keys in production. "
            "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )

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
    logger.info("Application shutting down gracefully")


def rate_limit_custom_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return project standard error JSON when client exceeds rate limits."""
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a new instance of the FastAPI application."""
    if settings is None:
        settings = get_settings()

    # Initialize the FastAPI app instance with metadata for OpenAPI documentation
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Reusable FastAPI backend template for computer-vision hackathons.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Attach slowapi rate limiter to app state and register exception handler
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, rate_limit_custom_handler)

    # Configure CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API route modules
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(users_router)

    return application


# Global application instance for ASGI servers (e.g., `uvicorn app.main:app`)
app = create_app()
