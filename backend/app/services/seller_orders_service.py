"""The boutique's fulfilment queue: only its own sub-orders, newest first."""

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFound, PermissionDenied
from app.core.permissions import Permission, assert_can
from app.models.commerce import Order, SubOrder
from app.models.user import User
from app.schemas.commerce import SellerSubOrder
from app.services import fulfilment_service as fs
from app.services.catalog_service import CatalogService
from app.services.order_service import events_out, item_out, review_ids


def _seller_id(user: User) -> uuid.UUID:
    assert_can(user, Permission.ORDER_FULFILL)
    if user.seller_id is None:  # boutique not approved yet
        raise PermissionDenied("Your boutique isn't approved yet.", code="seller_not_approved")
    return user.seller_id


def _with_lines(stmt):  # type: ignore[no-untyped-def]
    return stmt.options(
        selectinload(SubOrder.items), selectinload(SubOrder.events)
    ).execution_options(populate_existing=True)


async def counts(session: AsyncSession, user: User) -> dict[str, int]:
    seller_id = _seller_id(user)
    rows = await session.execute(
        select(SubOrder.status, func.count())
        .where(SubOrder.seller_id == seller_id)
        .group_by(SubOrder.status)
    )
    return {status: n for status, n in rows.all()}


async def queue(
    session: AsyncSession,
    catalog: CatalogService,
    user: User,
    *,
    status: str | None,
    limit: int,
    after: tuple[datetime, uuid.UUID] | None,
) -> tuple[list[SellerSubOrder], tuple[datetime, uuid.UUID] | None]:
    seller_id = _seller_id(user)
    stmt = select(SubOrder).where(SubOrder.seller_id == seller_id)
    if status:
        stmt = stmt.where(SubOrder.status == status)
    if after is not None:
        ts, sid = after
        stmt = stmt.where(
            or_(SubOrder.created_at < ts, and_(SubOrder.created_at == ts, SubOrder.id < sid))
        )
    rows = list(
        (
            await session.scalars(
                _with_lines(
                    stmt.order_by(SubOrder.created_at.desc(), SubOrder.id.desc()).limit(limit + 1)
                )
            )
        ).all()
    )
    more = len(rows) > limit
    rows = rows[:limit]
    out = await _out(session, catalog, rows)
    last = rows[-1] if more and rows else None
    return out, ((last.created_at, last.id) if last else None)


async def one(
    session: AsyncSession, catalog: CatalogService, user: User, sub_id: uuid.UUID
) -> SellerSubOrder:
    seller_id = _seller_id(user)
    sub = await session.scalar(_with_lines(select(SubOrder).where(SubOrder.id == sub_id)))
    if sub is None or sub.seller_id != seller_id:
        raise NotFound("We couldn't find that order.", code="order_not_found")
    return (await _out(session, catalog, [sub]))[0]


async def _out(
    session: AsyncSession, catalog: CatalogService, subs: list[SubOrder]
) -> list[SellerSubOrder]:
    if not subs:
        return []
    orders = {
        o.id: o
        for o in (
            await session.scalars(select(Order).where(Order.id.in_({s.order_id for s in subs})))
        ).all()
    }
    buyers = {
        u.id: u
        for u in (
            await session.scalars(
                select(User).where(User.id.in_({o.buyer_id for o in orders.values()}))
            )
        ).all()
    }
    reviews = await review_ids(session, [i.id for s in subs for i in s.items])
    out = []
    for s in subs:
        order = orders[s.order_id]
        buyer = buyers.get(order.buyer_id)
        out.append(
            SellerSubOrder(
                id=s.id,
                number=s.number,
                order_id=order.id,
                status=s.status,
                created_at=s.created_at,
                buyer_name=buyer.name if buyer else "Shopper",
                shipping_address=order.shipping_address,
                items_total_qc=s.items_total_qc,
                discount_qc=s.discount_qc,
                subtotal_qc=s.subtotal_qc,
                commission_qc=s.commission_qc,
                net_qc=s.subtotal_qc - s.commission_qc,
                voucher_code=s.voucher_code,
                tracking_no=s.tracking_no,
                return_reason=s.return_reason,
                shipped_at=s.shipped_at,
                delivered_at=s.delivered_at,
                auto_release_at=fs.auto_release_at(s),
                next=fs.next_for(s.status, fs.Actor.SELLER),
                items=[item_out(catalog, i, reviews, False) for i in s.items],
                events=events_out(s),
            )
        )
    return out
