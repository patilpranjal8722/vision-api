"""Database Declarative Base using modern SQLAlchemy 2.0 style.

All ORM models inherit from this Base class to share table metadata,
naming conventions, and type annotations.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all application database models."""

    pass
