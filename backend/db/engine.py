"""Async SQLAlchemy engine, session factory, and dependency."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _set_sqlite_pragmas(dbapi_conn, _connection_record) -> None:  # noqa: ANN001
    """Set SQLite pragmas on each new connection.

    - WAL mode: readers never block writers, writers never block readers
    - foreign_keys: enforce FK constraints (SQLite disables them by default)
    - synchronous=NORMAL: safe with WAL, faster than FULL
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def _make_engine(database_url: str):
    """Create an async engine from the given URL."""
    from sqlalchemy import event

    engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
    )

    # Apply SQLite pragmas on every raw connection
    if "sqlite" in database_url:
        event.listen(engine.sync_engine, "connect", _set_sqlite_pragmas)

    return engine


def _make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# Module-level singletons — replaced during lifespan startup
_engine = None
_async_session: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> None:
    """Initialize the module-level engine and session factory."""
    global _engine, _async_session
    _engine = _make_engine(database_url)
    _async_session = _make_session_factory(_engine)
    logger.info("Database engine initialized", extra={"database_url": database_url})


async def create_tables() -> None:
    """Create all tables defined in Base.metadata."""
    if _engine is None:
        raise RuntimeError("Engine not initialised. Call init_engine() first.")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an AsyncSession, close when done."""
    if _async_session is None:
        raise RuntimeError("Session factory not initialised. Call init_engine() first.")
    async with _async_session() as session:
        yield session
