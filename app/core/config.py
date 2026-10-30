"""Application configuration management using pydantic-settings.

Reads configuration from environment variables and an optional .env file.
Provides a cached `get_settings()` helper for dependency injection or direct usage.
"""

import json
from functools import lru_cache
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRET_PLACEHOLDER = "dev-insecure-secret-key-change-in-production-only-placeholder-32b"


class Settings(BaseSettings):
    """Configuration settings for vision-api application."""

    # Application Metadata
    APP_NAME: str = "vision-api"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Security & CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:5173",
    ]
    # SECRET_KEY must come only from the environment / .env file
    SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting (slowapi)
    LOGIN_RATE_LIMIT: str = "5/minute"
    RATE_LIMIT_ENABLED: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./vision_api.db"

    # Detector Settings
    DETECTOR_BACKEND: str = "dummy"
    MODEL_PATH: str = "models_store/yolov8n.pt"
    CONFIDENCE_THRESHOLD: float = 0.25
    MAX_UPLOAD_MB: int = 10
    MAX_IMAGE_DIMENSION: int = 6000
    ALLOWED_IMAGE_TYPES: Union[List[str], str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
    ]
    UPLOAD_DIR: str = "uploads"
    DEFAULT_REQUIRED_EQUIPMENT: str = "helmet,vest"
    CAMERA_NAME_MAX_LENGTH: int = 60

    # Video & Background Job Settings
    MAX_VIDEO_UPLOAD_MB: int = 100
    ALLOWED_VIDEO_TYPES: Union[List[str], str] = [
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "video/x-msvideo",
    ]
    FRAME_SKIP: int = 5
    MAX_CONCURRENT_JOBS: int = 2
    MAX_ACTIVE_JOBS_PER_USER: int = 3
    FRAME_READER_BACKEND: str = "dummy"
    DUMMY_FRAME_DELAY_MS: int = 20
    JOB_RUNNER_INLINE: bool = False

    # Alert, Analytics & WebSocket Settings
    ALERT_WARNING_THRESHOLD: int = 10
    ALERT_CRITICAL_THRESHOLD: int = 20
    ALERT_COOLDOWN_SECONDS: int = 30
    WS_AUTH_TIMEOUT_SECONDS: int = 5
    WS_MAX_FRAME_KB: int = 2048
    WS_MAX_CONNECTIONS_PER_USER: int = 3
    ANALYTICS_MAX_ROWS: int = 5000
    ANALYTICS_MAX_RANGE_DAYS: int = 90

    # Step 7: Hardening, Rate Limiting & Inference Protection Settings
    LOG_LEVEL: str = "INFO"
    MAX_REQUEST_BODY_KB: int = 1024
    DEFAULT_RATE_LIMIT: str = "120/minute"
    UPLOAD_RATE_LIMIT: str = "20/minute"
    REFRESH_RATE_LIMIT: str = "10/minute"
    INFERENCE_TIMEOUT_SECONDS: float = 30.0
    INFERENCE_WORKERS: int = 2
    INFERENCE_QUEUE_LIMIT: int = 8
    MAX_FRAME_FAILURE_RATIO: float = 0.5
    ENABLE_DOCS: bool = True
    SECURITY_HEADERS_ENABLED: bool = True

    # CV Service Integration Settings
    CV_SERVICE_URL: str = "http://127.0.0.1:9000"
    CV_SERVICE_API_KEY: str = ""
    CV_EVENTS_API_KEY: str = ""
    BACKEND_PUBLIC_URL: str = "http://127.0.0.1:8000"
    CV_CONTRACT_VERSION: str = "1.0"
    CV_EVENTS_MAX_BATCH: int = 100
    CV_EVENTS_MAX_BODY_KB: int = 512
    CV_JOB_MAX_AGE_MINUTES: int = 120

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Union[str, List[str]]) -> List[str]:
        """Allow origins to be specified as a JSON list string or a comma-separated string."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("ALLOWED_IMAGE_TYPES", mode="before")
    @classmethod
    def parse_allowed_image_types(cls, value: Union[str, List[str]]) -> List[str]:
        """Allow allowed image types to be specified as a JSON list string or a comma-separated string."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("ALLOWED_VIDEO_TYPES", mode="before")
    @classmethod
    def parse_allowed_video_types(cls, value: Union[str, List[str]]) -> List[str]:
        """Allow allowed video types to be specified as a JSON list string or a comma-separated string."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of the application Settings."""
    return Settings()
