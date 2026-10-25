"""Rate limiting setup using slowapi.

Behind a reverse proxy (e.g., Nginx, Traefik, AWS ALB), client IP addresses
are forwarded via the X-Forwarded-For header. To trust these proxy headers in production,
Uvicorn must be started with the `--proxy-headers` flag.

NOTE: Real-time WebSocket connections (/ws/*) are stateful streaming channels and are NOT
rate-limited by slowapi; they enforce per-user connection limits (WS_MAX_CONNECTIONS_PER_USER)
and cooldown throttling instead.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.DEFAULT_RATE_LIMIT],
    enabled=settings.RATE_LIMIT_ENABLED,
    headers_enabled=False,
)

