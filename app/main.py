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
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import get_logger, setup_logging

logger = get_logger("vision_api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager managing application startup and shutdown events.

    Beginner explanation:
    - Code before `yield`: Runs once when the application boots up.
      Use this for warm-up tasks like database connection pools or dummy detector checks.
    - `yield`: The application is actively running and handling client requests.
    - Code after `yield`: Runs once when the application is stopping.
      Use this for graceful cleanup, saving state, or releasing connections.
    """
    settings: Settings = get_settings()

    # --- Startup phase ---
    setup_logging(debug=settings.DEBUG)
    logger.info(
        "Application starting up",
        extra={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "detector_backend": settings.DETECTOR_BACKEND,
        },
    )

    yield

    # --- Shutdown phase ---
    logger.info("Application shutting down gracefully")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a new instance of the FastAPI application.

    Beginner explanation:
    - `FastAPI(title=..., lifespan=...)`: Instantiates the core web application.
    - `add_middleware(CORSMiddleware, ...)`: Configures browser security rules
      to permit frontend apps (e.g. running on localhost:3000) to communicate with this API.
    - `include_router(...)`: Registers route groups (e.g. /health, /api/v1/detect).
    """
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

    return application


# Global application instance for ASGI servers (e.g., `uvicorn app.main:app`)
app = create_app()
