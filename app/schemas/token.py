"""Authentication token schemas."""

from pydantic import BaseModel


class Token(BaseModel):
    """Schema returned upon successful authentication containing access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Schema for token refresh requests."""

    refresh_token: str
