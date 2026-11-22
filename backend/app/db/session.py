"""Async engine and session factory.

Routers receive a session through `get_session`. Services that move money open
their own `async with session.begin()` block so every ledger write is atomic.
"""

import asyncio
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_settings = get_settings()

engine: AsyncEngine = create_async_engine(
    _settings.database_url,
    echo=_settings.database_echo,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


PING_TIMEOUT_SECONDS = 1.5


async def ping_database() -> bool:
    """Return True if the database answers `SELECT 1` within PING_TIMEOUT_SECONDS.

    Bounded so the health check stays fast even when Postgres is unreachable
    (asyncpg's own connect timeout is 60s).
    """
    try:
        async with asyncio.timeout(PING_TIMEOUT_SECONDS), engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — health checks report, never raise
        return False
