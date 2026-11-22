"""In-app notification inbox (owner-scoped: users only ever see their own)."""

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.core.pagination import clamp_limit, decode_cursor, encode_cursor
from app.core.security import utcnow
from app.models.integration import Notification


async def list_for(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    cursor: str | None,
    limit: int | None,
    unread_only: bool,
) -> tuple[list[Notification], str | None]:
    size = clamp_limit(limit)
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    if pos := decode_cursor(cursor):
        created, last_id = datetime.fromisoformat(pos["created_at"]), uuid.UUID(pos["id"])
        stmt = stmt.where(
            (Notification.created_at < created)
            | ((Notification.created_at == created) & (Notification.id < last_id))
        )
    rows = list((await session.scalars(stmt.limit(size + 1))).all())
    next_cursor = None
    if len(rows) > size:
        rows = rows[:size]
        next_cursor = encode_cursor(
            {"created_at": rows[-1].created_at.isoformat(), "id": str(rows[-1].id)}
        )
    return rows, next_cursor


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count()).where(
                Notification.user_id == user_id, Notification.read_at.is_(None)
            )
        )
        or 0
    )


async def mark_read(
    session: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    row = await session.get(Notification, notification_id)
    if row is None or row.user_id != user_id:
        raise NotFound("We couldn't find that notification.")
    if row.read_at is None:
        row.read_at = utcnow()
        await session.commit()
    return row


async def mark_all_read(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    await session.commit()
