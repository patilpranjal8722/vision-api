"""Database engine, connection pooling, and session management.

For beginners learning SQLAlchemy & FastAPI:
1. Engine:
   The central communication hub connecting Python code to the underlying
   database (SQLite by default, PostgreSQL in production).
2. SQLite Specifics:
   - `check_same_thread=False`: SQLite restricts sharing connections across
     different threads by default. FastAPI handles requests on a thread pool,
     so we must disable this check to allow concurrent request handling.
   - `PRAGMA foreign_keys=ON`: In SQLite, foreign key constraints are turned
     OFF by default for backward compatibility. We hook into the connection
     event to turn them ON so cascading and integrity checks are enforced.
3. SessionLocal:
   A factory that instantiates a new database session whenever called.
4. get_db():
   A FastAPI dependency generator. It yields a fresh database session for
   each HTTP request and guarantees that `db.close()` runs after the request
   finishes (even if an error occurs).
"""

from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if is_sqlite:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=settings.DEBUG,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
        """Set SQLite PRAGMAs: foreign keys, WAL journal mode, busy timeout, and synchronous NORMAL."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )

# SessionLocal is the factory for creating individual database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session for an HTTP request.

    Guarantees that the session is always closed after request execution.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
