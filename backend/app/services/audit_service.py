"""Audit trail for admin actions and role changes (spec §7, enforcement layer 5).

Entries are only ever inserted, never updated or deleted. The caller commits,
so the audit row lands in the same transaction as the change it describes.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import clamp_limit, decode_cursor, encode_cursor
from app.models.user import AuditLog


def record(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: str | uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
    ip: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        before=before,
        after=after,
        reason=reason,
        ip=ip,
        created_at=datetime.now(UTC),
    )
    session.add(entry)
    return entry


async def list_entries(
    session: AsyncSession,
    *,
    cursor: str | None,
    limit: int | None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
) -> tuple[list[AuditLog], str | None]:
    size = clamp_limit(limit)
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if target_id:
        stmt = stmt.where(AuditLog.target_id == target_id)
    if pos := decode_cursor(cursor):
        created = datetime.fromisoformat(pos["created_at"])
        last_id = uuid.UUID(pos["id"])
        stmt = stmt.where(
            (AuditLog.created_at < created)
            | ((AuditLog.created_at == created) & (AuditLog.id < last_id))
        )
    rows = list((await session.scalars(stmt.limit(size + 1))).all())
    next_cursor = None
    if len(rows) > size:
        rows = rows[:size]
        last = rows[-1]
        next_cursor = encode_cursor({"created_at": last.created_at.isoformat(), "id": str(last.id)})
    return rows, next_cursor
