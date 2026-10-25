"""Structured logging configuration for vision-api.

Provides JSON-formatted / structured log output with timestamps, log levels,
logger names, request tracing, and redaction of sensitive credentials.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.context import get_request_id

# Set of sensitive credential keys to redact (case-insensitive)
SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "secret",
    "secret_key",
    "hashed_password",
}

STANDARD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message",
}


def redact_sensitive_data(obj: Any) -> Any:
    """Recursively redact dictionary entries matching sensitive credential keys."""
    if isinstance(obj, dict):
        return {
            k: "[REDACTED]" if str(k).lower() in SENSITIVE_KEYS else redact_sensitive_data(v)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [redact_sensitive_data(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(redact_sensitive_data(item) for item in obj)
    return obj


class SensitiveDataFilter(logging.Filter):
    """Logging filter that scrubs sensitive keys from dict messages and extras."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact dictionary in msg if applicable
        if isinstance(record.msg, dict):
            record.msg = redact_sensitive_data(record.msg)
        # Redact dictionary in args if applicable
        if isinstance(record.args, dict):
            record.args = redact_sensitive_data(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(
                redact_sensitive_data(arg) if isinstance(arg, dict) else arg
                for arg in record.args
            )

        # Redact extras attached to log record
        for k, v in list(record.__dict__.items()):
            if k not in STANDARD_ATTRS and not k.startswith("_"):
                if str(k).lower() in SENSITIVE_KEYS:
                    record.__dict__[k] = "[REDACTED]"
                elif isinstance(v, (dict, list, tuple)):
                    record.__dict__[k] = redact_sensitive_data(v)

        return True


class StructuredJsonFormatter(logging.Formatter):
    """Custom logging formatter that outputs logs as structured JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = get_request_id()

        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if req_id is not None:
            log_entry["request_id"] = req_id

        # Include exception details if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra attributes attached to the log record
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in STANDARD_ATTRS and not k.startswith("_")
        }
        if extras:
            log_entry["extra"] = redact_sensitive_data(extras)

        return json.dumps(log_entry, default=str)


def setup_logging(log_level_str: str = "INFO", debug: bool = False) -> None:
    """Configure root and third-party loggers for structured JSON output."""
    if debug:
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # Root handler writing to stdout with structured JSON format
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonFormatter())
    filter_instance = SensitiveDataFilter()
    handler.addFilter(filter_instance)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.addFilter(filter_instance)

    # Quiet overly chatty loggers while preserving warnings
    for noisy_logger in ("uvicorn.access", "uvicorn.error"):
        noisy = logging.getLogger(noisy_logger)
        noisy.handlers.clear()
        noisy.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Retrieve a logger configured with structured formatting."""
    return logging.getLogger(name)
