"""Seller Studio: the fulfilment queue (Phase 7). Phase 8 adds the rest."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.api.deps import AppSettings, DbSession, SessionFactoryDep, require_permission
from app.core.pagination import clamp_limit, decode_keyset, encode_keyset
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.commerce import SellerQueue, SellerSubOrder, SubStatus, TransitionRequest
from app.services import email_service
from app.services import fulfilment_service as fs
from app.services import seller_orders_service as sos
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/seller", tags=["seller"])

Fulfiller = Depends(require_permission(Permission.ORDER_FULFILL))


@router.get("/orders", response_model=SellerQueue, summary="Your boutique's orders")
async def orders(
    session: DbSession,
    settings: AppSettings,
    status: SubStatus | None = None,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=96)] = None,
    user: User = Fulfiller,
) -> SellerQueue:
    items, last = await sos.queue(
        session,
        CatalogService(session, settings),
        user,
        status=status,
        limit=clamp_limit(limit or 20),
        after=decode_keyset(cursor),
    )
    return SellerQueue(
        items=items,
        counts=await sos.counts(session, user),
        next_cursor=encode_keyset(last),
        has_more=last is not None,
    )


@router.get("/orders/{sub_id}", response_model=SellerSubOrder, summary="One order")
async def order(
    sub_id: uuid.UUID, session: DbSession, settings: AppSettings, user: User = Fulfiller
) -> SellerSubOrder:
    return await sos.one(session, CatalogService(session, settings), user, sub_id)


@router.post(
    "/orders/{sub_id}/status",
    response_model=SellerSubOrder,
    summary="Advance an order (processing, shipped, delivered, cancel, approve/decline a return)",
)
async def move(
    sub_id: uuid.UUID,
    body: TransitionRequest,
    background: BackgroundTasks,
    session: DbSession,
    settings: AppSettings,
    session_factory: SessionFactoryDep,
    user: User = Fulfiller,
) -> SellerSubOrder:
    moved = await fs.transition(
        session,
        settings,
        user,
        sub_id,
        body.to,
        note=body.note,
        tracking_no=body.tracking_no,
        reason=body.note,
    )
    for email in moved.emails:
        background.add_task(email_service.deliver, session_factory, email.id, settings)
    return await sos.one(session, CatalogService(session, settings), user, sub_id)
