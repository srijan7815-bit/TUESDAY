"""Async SQLAlchemy engine/session."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.models.base import Base

_engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _make_engine():
    settings = get_settings()
    url = settings.tuesday_database_url
    # Render supplies a standard PostgreSQL URL; SQLAlchemy async needs asyncpg.
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    connect_args: dict = {}
    if url.startswith("sqlite"):
        # timeout is in seconds for the pysqlite lock wait
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
    engine = create_async_engine(
        url,
        echo=False,
        future=True,
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    if url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_on_connect(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


async def init_db() -> None:
    global _engine, async_session_factory
    if _engine is None:
        _engine = _make_engine()
        async_session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
    assert _engine is not None
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if str(_engine.url).startswith("sqlite"):
            await conn.execute(text("PRAGMA journal_mode=WAL"))


async def get_session() -> AsyncIterator[AsyncSession]:
    if async_session_factory is None:
        await init_db()
    assert async_session_factory is not None
    async with async_session_factory() as session:
        yield session


async def session_scope() -> AsyncIterator[AsyncSession]:
    """Standalone session for long-lived generators (SSE)."""
    if async_session_factory is None:
        await init_db()
    assert async_session_factory is not None
    async with async_session_factory() as session:
        yield session
