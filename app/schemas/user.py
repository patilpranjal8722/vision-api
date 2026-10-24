"""User schemas for request validation and response serialization."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


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
        min_length=8,
        max_length=128,
        description="Password must be between 8 and 128 characters.",
    )


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
