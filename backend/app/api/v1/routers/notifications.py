import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import CursorPage
from app.schemas.notifications import NotificationOut, UnreadCount
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=CursorPage[NotificationOut], summary="Your inbox, newest first")
async def list_notifications(
    user: CurrentUser,
    session: DbSession,
    cursor: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=96),
    unread: bool = False,
) -> CursorPage[NotificationOut]:
    rows, next_cursor = await notification_service.list_for(
        session, user.id, cursor=cursor, limit=limit, unread_only=unread
    )
    return CursorPage[NotificationOut](
        items=[NotificationOut.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.get("/unread-count", response_model=UnreadCount, summary="Badge count")
async def unread_count(user: CurrentUser, session: DbSession) -> UnreadCount:
    return UnreadCount(unread=await notification_service.unread_count(session, user.id))


@router.post("/{notification_id}/read", response_model=NotificationOut, summary="Mark one read")
async def mark_read(
    notification_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> NotificationOut:
    return NotificationOut.model_validate(
        await notification_service.mark_read(session, user.id, notification_id)
    )


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT, summary="Mark all read")
async def mark_all_read(user: CurrentUser, session: DbSession) -> None:
    await notification_service.mark_all_read(session, user.id)
