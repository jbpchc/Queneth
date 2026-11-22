"""Checkout and the buyer's orders."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, status

from app.api.deps import AppSettings, DbSession, SessionFactoryDep, require_permission
from app.core.pagination import clamp_limit, decode_keyset, encode_keyset
from app.core.permissions import Permission
from app.core.rate_limit import limiter
from app.models.commerce import OrderStatus
from app.models.user import User
from app.schemas.commerce import (
    CancelRequest,
    CheckoutRequest,
    OrderOut,
    OrderSummary,
    ReturnRequest,
)
from app.schemas.common import CursorPage
from app.services import email_service, order_service
from app.services import fulfilment_service as fs
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/orders", tags=["orders"])

Buyer = Depends(require_permission(Permission.ORDER_CHECKOUT))
Viewer = Depends(require_permission(Permission.ORDER_VIEW))
IdemKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=80,
        description="Unique per checkout attempt. Retrying with it never charges twice.",
    ),
]


@router.post(
    "/checkout",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Pay for the bag with QueWallet (split per boutique, held in escrow)",
    responses={
        402: {"description": "Not used: QueWallet is the only payment method."},
        409: {"description": "empty_bag, stock_changed, prices_changed, insufficient_funds"},
    },
)
@limiter.limit("10/minute")
async def checkout(
    request: Request,
    body: CheckoutRequest,
    idempotency_key: IdemKey,
    background: BackgroundTasks,
    session: DbSession,
    settings: AppSettings,
    session_factory: SessionFactoryDep,
    user: User = Buyer,
) -> OrderOut:
    order, email = await order_service.checkout(session, settings, user, body, idempotency_key)
    if email is not None:
        background.add_task(email_service.deliver, session_factory, email.id, settings)
    return await order_service.to_out(session, CatalogService(session, settings), order, user)


@router.get("", response_model=CursorPage[OrderSummary], summary="Your orders, newest first")
async def list_orders(
    session: DbSession,
    settings: AppSettings,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=96)] = None,
    user: User = Viewer,
) -> CursorPage[OrderSummary]:
    items, last = await order_service.list_for(
        session,
        CatalogService(session, settings),
        user,
        limit=clamp_limit(limit or 12),
        after=decode_keyset(cursor),
    )
    return CursorPage[OrderSummary](
        items=items, next_cursor=encode_keyset(last), has_more=last is not None
    )


@router.get("/{order_id}", response_model=OrderOut, summary="One of your orders")
async def get_order(
    order_id: uuid.UUID, session: DbSession, settings: AppSettings, user: User = Viewer
) -> OrderOut:
    order = await order_service.get_for(session, user, order_id)
    return await order_service.to_out(session, CatalogService(session, settings), order, user)


# ─── Buyer actions on one boutique's part of an order ──────────────────────


async def _after(
    moved: fs.Moved,
    session: DbSession,
    settings: AppSettings,
    session_factory: SessionFactoryDep,
    background: BackgroundTasks,
    user: User,
) -> OrderOut:
    for email in moved.emails:
        background.add_task(email_service.deliver, session_factory, email.id, settings)
    order = await order_service.get_for(session, user, moved.sub.order_id)
    return await order_service.to_out(session, CatalogService(session, settings), order, user)


@router.post(
    "/sub-orders/{sub_id}/cancel",
    response_model=OrderOut,
    summary="Cancel before shipping (escrow refunded, stock restored)",
)
async def cancel(
    sub_id: uuid.UUID,
    body: CancelRequest,
    background: BackgroundTasks,
    session: DbSession,
    settings: AppSettings,
    session_factory: SessionFactoryDep,
    user: User = Viewer,
) -> OrderOut:
    moved = await fs.transition(
        session, settings, user, sub_id, OrderStatus.CANCELLED.value, reason=body.reason
    )
    return await _after(moved, session, settings, session_factory, background, user)


@router.post(
    "/sub-orders/{sub_id}/received",
    response_model=OrderOut,
    summary="Mark received (escrow released to the boutique, Que Points earned)",
)
async def received(
    sub_id: uuid.UUID,
    background: BackgroundTasks,
    session: DbSession,
    settings: AppSettings,
    session_factory: SessionFactoryDep,
    user: User = Viewer,
) -> OrderOut:
    moved = await fs.transition(session, settings, user, sub_id, OrderStatus.COMPLETED.value)
    return await _after(moved, session, settings, session_factory, background, user)


@router.post(
    "/sub-orders/{sub_id}/return",
    response_model=OrderOut,
    summary="Request a return within 7 days of delivery",
)
async def request_return(
    sub_id: uuid.UUID,
    body: ReturnRequest,
    background: BackgroundTasks,
    session: DbSession,
    settings: AppSettings,
    session_factory: SessionFactoryDep,
    user: User = Viewer,
) -> OrderOut:
    moved = await fs.transition(
        session, settings, user, sub_id, OrderStatus.RETURN_REQUESTED.value, reason=body.reason
    )
    return await _after(moved, session, settings, session_factory, background, user)
