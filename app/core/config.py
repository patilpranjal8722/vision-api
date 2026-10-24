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
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
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
