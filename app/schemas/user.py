"""User schemas for request validation and response serialization."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    validate_password_strength,
)


class UserCreate(BaseModel):
    """Schema for user registration requests.

    Note: The `role` field is deliberately excluded to prevent privilege escalation.
    All users registered via this schema are assigned the 'user' role by default.
    """

    email: EmailStr
    username: str = Field(
        min_length=3,
        max_length=30,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="3-30 characters, letters, digits, and underscores only.",
    )
    password: str = Field(
        description=(
            f"Password must be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters long "
            "and contain at least one uppercase letter, one lowercase letter, one digit, and one special character."
        ),
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength rules."""
        unmet_rules = validate_password_strength(v)
        if unmet_rules:
            raise ValueError("; ".join(unmet_rules))
        return v


class UserOut(BaseModel):
    """Public user response schema.

    Excludes sensitive credentials such as `hashed_password`.
    """

    id: int
    email: EmailStr
    username: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
