"""
SQLAlchemy engine, session factory, and Base class.

SQLite-specific settings applied on every new connection:
  - WAL journal mode  → allows concurrent reads during writes
  - Foreign keys ON   → enforce FK constraints (SQLite disables them by default)
"""
import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from hr_agent.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def _build_engine():
    settings = get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(settings.database_url, connect_args=connect_args)

    if settings.database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    Create all tables that are not yet present in the database.
    In production use `alembic upgrade head` instead.
    Models must be imported before this is called so SQLAlchemy's metadata
    knows about them — main.py handles this via the models package import.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialised.")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a per-request DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
