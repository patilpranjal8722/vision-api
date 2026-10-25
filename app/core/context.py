"""Context variables for request tracing and contextual logging."""

import contextvars
from typing import Optional

request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> Optional[str]:
    """Retrieve current request ID from contextvar if available."""
    return request_id_ctx.get()


def set_request_id(req_id: str) -> contextvars.Token:
    """Store request ID in contextvar and return token for resetting."""
    return request_id_ctx.set(req_id)


def reset_request_id(token: contextvars.Token) -> None:
    """Reset request ID contextvar to its previous state."""
    request_id_ctx.reset(token)
