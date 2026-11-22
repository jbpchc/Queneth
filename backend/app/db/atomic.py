"""`atomic(session)`: one database transaction around a unit of work.

Request sessions often already have a transaction open (the auth dependency
loaded the user), so `session.begin()` would fail. This helper commits on
success and rolls back on any exception either way, which is what spec §3
asks of every money movement ("one database transaction").
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def atomic(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    if not session.in_transaction():
        async with session.begin():
            yield session
        return
    try:
        yield session
    except BaseException:
        await session.rollback()
        raise
    else:
        await session.commit()
