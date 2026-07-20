"""
database.py — Async SQLAlchemy engine + session factory.

Single source of truth for database connectivity.
The `get_db` FastAPI dependency yields an `AsyncSession` and handles
commit/rollback automatically. `init_db` is called once at startup
to run Alembic migrations.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Declarative base — shared by all ORM models
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""


# ---------------------------------------------------------------------------
# Engine & session factory — lazy-initialized at first call
# ---------------------------------------------------------------------------

_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            pool_pre_ping=True,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=_get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_session_factory


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an `AsyncSession` for the request lifecycle.

    Commits on success, rolls back on any unhandled exception.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Context manager variant (for use outside FastAPI request context)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a session (for background workers)."""
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Startup helper
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Create all tables (used in tests / first-run without Alembic)."""
    # Import all models so Base.metadata is populated before create_all
    import src.auto_reply.infrastructure.models  # noqa: F401

    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
    logger.info("database initialized url=%s", get_settings().database_url)


def _add_missing_columns(connection) -> None:
    """Add columns that exist on the models but not yet in the database.

    `create_all` creates missing *tables* but never alters existing ones, so a
    new column on a model that already has a table is silently absent and every
    query then fails with "no such column". Deleting the database is the usual
    workaround, but it now also destroys the stored Gmail OAuth tokens — so the
    columns are patched in instead.

    Deliberately narrow: additive `ALTER TABLE ... ADD COLUMN` only, which
    SQLite supports and which cannot lose data. Anything else (dropping,
    retyping, constraints) belongs in a real Alembic migration.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all just made it; it is already current

        present = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue

            # A NOT NULL column cannot be added to a table with existing rows
            # without a default — that needs a real migration, not a guess.
            if not column.nullable and column.server_default is None:
                logger.warning(
                    "column %s.%s is missing and NOT NULL — needs a migration",
                    table.name,
                    column.name,
                )
                continue

            ddl = column.type.compile(connection.dialect)
            connection.execute(
                text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {ddl}')
            )
            logger.info("added missing column %s.%s", table.name, column.name)


async def close_db() -> None:
    """Dispose the engine connection pool (called on shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("database connection pool closed")
