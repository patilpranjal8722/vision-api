"""Structured logging configuration for vision-api.

Provides JSON-formatted / structured log output with timestamps, log levels,
logger names, and contextual fields without relying on raw print statements.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class StructuredJsonFormatter(logging.Formatter):
    """Custom logging formatter that outputs logs as structured JSON strings."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include exception details if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include any extra attributes attached to the log record
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message",
        }
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }
        if extras:
            log_entry["extra"] = extras

        return json.dumps(log_entry, default=str)


def setup_logging(debug: bool = False) -> None:
    """Configure root and third-party loggers for structured output."""
    log_level = logging.DEBUG if debug else logging.INFO

    # Root handler writing to stdout with structured JSON format
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJsonFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quiet overly chatty loggers while preserving warnings
    for noisy_logger in ("uvicorn.access", "uvicorn.error"):
        logging.getLogger(noisy_logger).handlers.clear()
        logging.getLogger(noisy_logger).propagate = True


def get_logger(name: str) -> logging.Logger:
    """Retrieve a logger configured with the structured formatting."""
    return logging.getLogger(name)
