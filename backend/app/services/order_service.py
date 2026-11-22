"""Checkout and order reads.

Checkout (spec §11) is one atomic unit of work:

1. The buyer's PIN is verified first (wrong tries are recorded even though
   checkout stops).
2. Bag rows and their variants are locked (``FOR UPDATE``); stock, visibility,
   the own-boutique rule and vouchers are re-checked on the server.
3. The server total must equal the total the buyer reviewed, or checkout stops
   with ``prices_changed`` (409) and nothing is charged.
4. One Order is created, split into one SubOrder per boutique; each sub-order
   is paid into escrow with its own ledger transaction.
5. Stock is decremented, vouchers are redeemed, bought items leave the bag,
   and the confirmation email and seller notifications are queued.

Any failure rolls everything back. The ``Idempotency-Key`` makes a retried or
double-clicked Pay return the first order instead of charging twice.
"""

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.errors import Conflict, NotFound
from app.core.permissions import Permission, assert_can, can
from app.core.security import utcnow
from app.db.atomic import atomic
from app.models.catalog import CartItem, Product, Review, SellerProfile, Variant
from app.models.commerce import (
    CartVoucher,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusEvent,
    SubOrder,
    Voucher,
    VoucherRedemption,
)
from app.models.integration import EmailLog, Notification
from app.models.user import User
from app.schemas.catalog import Ref
from app.schemas.commerce import (
    CheckoutRequest,
    OrderItemOut,
    OrderOut,
    OrderSummary,
    StatusEventOut,
    SubOrderOut,
)
from app.services import address_service, email_service, email_templates, voucher_service
from app.services import fulfilment_service as fs
from app.services import wallet_service as ws
from app.services.catalog_index import refresh_denormalized
from app.services.catalog_service import CatalogService

POINTS_PER_QC = 100  # 1 Que Point per 100 QC spent, credited on delivery (Phase 7)


@dataclass
class _Line:
    cart_item: CartItem
    variant: Variant
    product: Product

    @property
    def total(self) -> int:
        return self.variant.price_qc * self.cart_item.qty


@dataclass
class _Group:
    seller: SellerProfile
    lines: list[_Line] = field(default_factory=list)
    voucher: Voucher | None = None
    discount: int = 0

    @property
    def items_total(self) -> int:
        return sum(line.total for line in self.lines)

    @property
    def subtotal(self) -> int:
        return self.items_total - self.discount


def _full(stmt):  # type: ignore[no-untyped-def]
    """Order with sub-orders, items and events loaded fresh (async: no lazy IO)."""
    subs = selectinload(Order.sub_orders)
    return stmt.options(
        subs.selectinload(SubOrder.items), subs.selectinload(SubOrder.events)
    ).execution_options(populate_existing=True)


async def _by_key(session: AsyncSession, key: str) -> Order | None:
    return await session.scalar(_full(select(Order).where(Order.idempotency_key == key)))


async def _load(session: AsyncSession, order_id: uuid.UUID) -> Order | None:
    return await session.scalar(_full(select(Order).where(Order.id == order_id)))


async def _new_number(session: AsyncSession) -> str:
    """QN-2026-4821: short enough to read aloud (UX: Miller's Law)."""
    year = utcnow().year
    for digits in (4, 4, 4, 5, 6):
        number = f"QN-{year}-{secrets.randbelow(9 * 10 ** (digits - 1)) + 10 ** (digits - 1)}"
        if await session.scalar(select(Order.id).where(Order.number == number)) is None:
            return number
    raise Conflict("Please try again.", code="order_number_busy")  # pragma: no cover


async def _lock_bag(session: AsyncSession, user: User) -> list[_Line]:
    rows = (
        await session.execute(
            select(CartItem, Variant, Product)
            .join(Variant, Variant.id == CartItem.variant_id)
            .join(Product, Product.id == Variant.product_id)
            .where(CartItem.user_id == user.id, CartItem.saved_for_later.is_(False))
            .order_by(Variant.id)  # stable lock order: no deadlocks between buyers
            .with_for_update(of=Variant)
        )
    ).all()
    return [_Line(c, v, p) for c, v, p in rows]


def _check_lines(user: User, lines: list[_Line]) -> None:
    if not lines:
        raise Conflict("Your bag is empty.", code="empty_bag")
    now = utcnow()
    problems: list[dict[str, object]] = []
    for line in lines:
        p, v, qty = line.product, line.variant, line.cart_item.qty
        if user.seller_id is not None and p.seller_id == user.seller_id:
            raise Conflict("You can't buy from your own boutique.", code="own_product")
        visible = (
            p.status == "active"
            and p.deleted_at is None
            and p.published_at is not None
            and p.published_at <= now
            and p.seller.status == "approved"
        )
        if not visible or v.stock < qty:
            problems.append(
                {
                    "cart_item_id": str(line.cart_item.id),
                    "title": p.title,
                    "available": v.stock if visible else 0,
                }
            )
    if problems:
        raise Conflict(
            "Some pieces in your bag just sold out or changed. Review your bag and try again.",
            code="stock_changed",
            details={"items": problems},
        )


async def _group(session: AsyncSession, user: User, lines: list[_Line]) -> list[_Group]:
    groups: dict[uuid.UUID, _Group] = {}
    for line in lines:
        groups.setdefault(line.product.seller_id, _Group(seller=line.product.seller)).lines.append(
            line
        )
    applied = await voucher_service.applied(session, user.id)
    if applied:
        # Lock the vouchers we'll redeem so max_uses can't be overrun.
        ids = [v.id for sid, v in applied.items() if sid in groups]
        locked = {
            v.id: v
            for v in (
                await session.scalars(
                    select(Voucher)
                    .where(Voucher.id.in_(ids))
                    .order_by(Voucher.id)
                    .with_for_update()
                )
            ).all()
        }
        redeemed = await voucher_service.redeemed_ids(session, user.id)
        for seller_id, group in groups.items():
            voucher = locked.get(applied[seller_id].id) if seller_id in applied else None
            if voucher is None:
                continue
            result = voucher_service.evaluate(
                voucher, group.items_total, redeemed=voucher.id in redeemed
            )
            if result.problem is None and result.discount_qc > 0:
                group.voucher, group.discount = voucher, result.discount_qc
    return sorted(groups.values(), key=lambda g: g.seller.boutique_name)


async def checkout(
    session: AsyncSession,
    settings: Settings,
    user: User,
    body: CheckoutRequest,
    idempotency_key: str,
) -> tuple[Order, EmailLog | None]:
    """Returns the order and the confirmation email to deliver (None on replay)."""
    assert_can(user, Permission.ORDER_CHECKOUT)
    key = f"checkout:{user.id}:{idempotency_key}"
    if (existing := await _by_key(session, key)) is not None:
        return existing, None

    address = await address_service.owned(session, user, body.address_id)
    wallet = await ws.user_wallet(session, user.id)
    await ws.verify_pin(session, wallet, body.pin)

    try:
        async with atomic(session):
            lines = await _lock_bag(session, user)
            _check_lines(user, lines)
            groups = await _group(session, user, lines)
            subtotal = sum(g.items_total for g in groups)
            discount = sum(g.discount for g in groups)
            total = subtotal - discount
            if total != body.expected_total_qc:
                raise Conflict(
                    "Prices or vouchers changed since you reviewed your order. "
                    "Check the new total before paying.",
                    code="prices_changed",
                    details={"total_qc": total, "expected_total_qc": body.expected_total_qc},
                )
            if wallet.balance_qc < total:
                raise ws.InsufficientFunds(
                    details={
                        "balance_qc": wallet.balance_qc,
                        "shortfall_qc": total - wallet.balance_qc,
                    }
                )

            order = Order(
                id=uuid.uuid4(),
                buyer_id=user.id,
                number=await _new_number(session),
                subtotal_qc=subtotal,
                discount_qc=discount,
                total_qc=total,
                shipping_address=address.snapshot(),
                idempotency_key=key,
                status=OrderStatus.PAID.value,
                points_pending=total // POINTS_PER_QC,
            )
            session.add(order)
            await session.flush()

            now = utcnow()
            touched: dict[uuid.UUID, Product] = {}
            for n, group in enumerate(groups, start=1):
                sub = SubOrder(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    seller_id=group.seller.id,
                    number=f"{order.number}-{n:02}",
                    items_total_qc=group.items_total,
                    discount_qc=group.discount,
                    subtotal_qc=group.subtotal,
                    commission_qc=ws.commission_for(group.subtotal),
                    voucher_code=group.voucher.code if group.voucher else None,
                    status=OrderStatus.PAID.value,
                )
                session.add(sub)
                session.add(
                    OrderStatusEvent(
                        sub_order_id=sub.id,
                        from_status=None,
                        to_status=OrderStatus.PAID.value,
                        actor_id=user.id,
                        note="Paid with QueWallet. Held in escrow until delivery.",
                        created_at=now,
                    )
                )
                for line in group.lines:
                    p, v, qty = line.product, line.variant, line.cart_item.qty
                    image = p.images[0].url if p.images else None
                    session.add(
                        OrderItem(
                            sub_order_id=sub.id,
                            product_id=p.id,
                            variant_id=v.id,
                            title_snapshot=p.title,
                            brand_snapshot=p.brand.name,
                            options_snapshot=dict(v.options),
                            image_snapshot=image,
                            product_slug=p.slug,
                            unit_price_qc=v.price_qc,
                            qty=qty,
                            line_total_qc=line.total,
                        )
                    )
                    v.stock -= qty
                    touched[p.id] = p
                if group.voucher is not None:
                    group.voucher.used_count += 1
                    session.add(
                        VoucherRedemption(
                            voucher_id=group.voucher.id,
                            user_id=user.id,
                            sub_order_id=sub.id,
                            discount_qc=group.discount,
                        )
                    )
                await session.flush()
                if group.subtotal > 0:
                    tx = await ws.pay_into_escrow(
                        session,
                        user.id,
                        group.subtotal,
                        f"order:{order.id}:sub:{n}:pay",
                        memo=f"Order {sub.number} · {group.seller.boutique_name}",
                        meta={"order_id": str(order.id), "sub_order_id": str(sub.id)},
                    )
                    sub.payment_tx_id = tx.id

            # Bought pieces leave the bag; used vouchers are cleared.
            await session.execute(
                delete(CartItem).where(
                    CartItem.id.in_([line.cart_item.id for g in groups for line in g.lines])
                )
            )
            await session.execute(
                delete(CartVoucher).where(
                    CartVoucher.user_id == user.id,
                    CartVoucher.voucher_id.in_(
                        select(Voucher.id).where(
                            Voucher.seller_id.in_([g.seller.id for g in groups])
                        )
                    ),
                )
            )
            await session.flush()
            for product in touched.values():
                variants = list(
                    (
                        await session.scalars(
                            select(Variant).where(Variant.product_id == product.id)
                        )
                    ).all()
                )
                refresh_denormalized(product, variants)

            entry = _notify(session, settings, user, order, groups)
    except IntegrityError:
        # A concurrent duplicate with the same key won the race: return its order.
        await session.rollback()
        if (existing := await _by_key(session, key)) is not None:
            return existing, None
        raise
    loaded = await _load(session, order.id)
    assert loaded is not None
    return loaded, entry


def _notify(
    session: AsyncSession, settings: Settings, user: User, order: Order, groups: list[_Group]
) -> EmailLog:
    path = f"/account/orders/{order.id}"
    email = email_templates.order_confirmation(
        name=user.name,
        number=order.number,
        total_qc=order.total_qc,
        points=order.points_pending,
        boutiques=[
            (
                g.seller.boutique_name,
                [(ln.product.title, ln.cart_item.qty, ln.total) for ln in g.lines],
            )
            for g in groups
        ],
        url=f"{settings.frontend_url}{path}",
        inbox_path=path,
    )
    entry = email_service.queue(session, user=user, to_email=user.email, email=email)
    for n, g in enumerate(groups, start=1):
        pieces = sum(ln.cart_item.qty for ln in g.lines)
        session.add(
            Notification(
                user_id=g.seller.user_id,
                type="order.new",
                payload={
                    "title": f"New order {order.number}-{n:02}",
                    "body": f"{pieces} {'piece' if pieces == 1 else 'pieces'} · "
                    f"{g.subtotal:,} QC held in escrow until delivery.",
                    "action_url": "/seller",
                },
            )
        )
    return entry


# ─── Reads ─────────────────────────────────────────────────────────────────


async def get_for(session: AsyncSession, user: User, order_id: uuid.UUID) -> Order:
    """Buyers see their own orders; admins see any. Others get 404 (no IDOR)."""
    assert_can(user, Permission.ORDER_VIEW)
    order = await _load(session, order_id)
    if order is None or not can(user, Permission.ORDER_VIEW, order):
        raise NotFound("We couldn't find that order.", code="order_not_found")
    return order


REVIEWABLE = {OrderStatus.DELIVERED.value, OrderStatus.COMPLETED.value}
FINISHED = {OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value, OrderStatus.REFUNDED.value}


async def review_ids(
    session: AsyncSession, item_ids: list[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    if not item_ids:
        return {}
    rows = await session.execute(
        select(Review.order_item_id, Review.id).where(Review.order_item_id.in_(item_ids))
    )
    return {item_id: rid for item_id, rid in rows.all() if item_id is not None}


def item_out(
    catalog: CatalogService, i: OrderItem, reviews: dict[uuid.UUID, uuid.UUID], reviewable: bool
) -> OrderItemOut:
    rid = reviews.get(i.id)
    return OrderItemOut(
        id=i.id,
        title=i.title_snapshot,
        brand=i.brand_snapshot,
        options=i.options_snapshot,
        image=catalog.abs_url(i.image_snapshot),
        product_slug=i.product_slug,
        unit_price_qc=i.unit_price_qc,
        qty=i.qty,
        line_total_qc=i.line_total_qc,
        review_id=rid,
        can_review=reviewable and rid is None,
    )


def events_out(sub: SubOrder) -> list[StatusEventOut]:
    return [
        StatusEventOut(
            from_status=e.from_status, to_status=e.to_status, note=e.note, created_at=e.created_at
        )
        for e in sub.events
    ]


async def to_out(
    session: AsyncSession, catalog: CatalogService, order: Order, viewer: User | None = None
) -> OrderOut:
    """`viewer` = the buyer looking at it: their available actions are included."""
    sellers = {
        s.id: s
        for s in (
            await session.scalars(
                select(SellerProfile).where(
                    SellerProfile.id.in_([so.seller_id for so in order.sub_orders])
                )
            )
        ).all()
    }
    is_buyer = viewer is not None and viewer.id == order.buyer_id
    reviews = await review_ids(session, [i.id for so in order.sub_orders for i in so.items])
    now = utcnow()
    subs = []
    for so in order.sub_orders:
        seller = sellers[so.seller_id]
        reviewable = is_buyer and so.status in REVIEWABLE
        subs.append(
            SubOrderOut(
                id=so.id,
                number=so.number,
                status=so.status,
                boutique=Ref(name=seller.boutique_name, slug=seller.slug),
                boutique_logo=catalog.abs_url(seller.logo_url),
                items_total_qc=so.items_total_qc,
                discount_qc=so.discount_qc,
                subtotal_qc=so.subtotal_qc,
                voucher_code=so.voucher_code,
                tracking_no=so.tracking_no,
                shipped_at=so.shipped_at,
                delivered_at=so.delivered_at,
                escrow_released_at=so.escrow_released_at,
                return_reason=so.return_reason,
                return_deadline=fs.return_deadline(so),
                auto_release_at=fs.auto_release_at(so),
                actions=fs.buyer_actions(so, now) if is_buyer else [],
                items=[item_out(catalog, i, reviews, reviewable) for i in so.items],
                events=events_out(so),
            )
        )
    earned = sum(
        so.subtotal_qc // POINTS_PER_QC
        for so in order.sub_orders
        if so.status == OrderStatus.COMPLETED.value
    )
    pending = sum(
        so.subtotal_qc // POINTS_PER_QC for so in order.sub_orders if so.status not in FINISHED
    )
    return OrderOut(
        id=order.id,
        number=order.number,
        status=order.status,
        subtotal_qc=order.subtotal_qc,
        discount_qc=order.discount_qc,
        total_qc=order.total_qc,
        points_pending=pending,
        points_earned=earned,
        shipping_address=order.shipping_address,
        created_at=order.created_at,
        sub_orders=subs,
    )


async def list_for(
    session: AsyncSession,
    catalog: CatalogService,
    user: User,
    *,
    limit: int,
    after: tuple[datetime, uuid.UUID] | None,
) -> tuple[list[OrderSummary], tuple[datetime, uuid.UUID] | None]:
    """The buyer's own orders, newest first (keyset pagination)."""
    assert_can(user, Permission.ORDER_VIEW)
    stmt = select(Order).where(Order.buyer_id == user.id)
    if after is not None:
        ts, oid = after
        stmt = stmt.where(or_(Order.created_at < ts, and_(Order.created_at == ts, Order.id < oid)))
    rows = list(
        (
            await session.scalars(
                _full(stmt.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit + 1))
            )
        ).all()
    )
    more = len(rows) > limit
    rows = rows[:limit]
    seller_ids = {so.seller_id for o in rows for so in o.sub_orders}
    names = (
        {
            s.id: s.boutique_name
            for s in (
                await session.scalars(select(SellerProfile).where(SellerProfile.id.in_(seller_ids)))
            ).all()
        }
        if seller_ids
        else {}
    )
    out: list[OrderSummary] = []
    for o in rows:
        items = [i for so in o.sub_orders for i in so.items]
        out.append(
            OrderSummary(
                id=o.id,
                number=o.number,
                status=o.status,
                total_qc=o.total_qc,
                item_count=sum(i.qty for i in items),
                boutiques=[names.get(so.seller_id, "") for so in o.sub_orders],
                preview_images=[
                    url for i in items[:4] if (url := catalog.abs_url(i.image_snapshot))
                ],
                created_at=o.created_at,
            )
        )
    last = rows[-1] if more and rows else None
    return out, ((last.created_at, last.id) if last else None)
