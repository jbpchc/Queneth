"""Seller Studio: dashboard, earnings, drops, vouchers and review replies.
Everything is scoped to the seller's own boutique."""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Permission, assert_can
from app.core.security import as_aware, utcnow
from app.core.text import slugify
from app.models.catalog import (
    Drop,
    DropSubscription,
    Product,
    Review,
    SellerProfile,
    Variant,
    drop_products,
)
from app.models.commerce import OrderItem, OrderStatus, SubOrder, Voucher, VoucherRedemption
from app.models.integration import Notification
from app.models.user import User
from app.models.wallet import LedgerEntry, LedgerTransaction, TxType
from app.schemas.studio import (
    Dashboard,
    DayPoint,
    DropIn,
    Earnings,
    Funnel,
    LowStock,
    Payout,
    StudioDrop,
    StudioReview,
    StudioVoucher,
    TopProduct,
    VoucherIn,
    VoucherPatch,
)
from app.services import email_service, email_templates
from app.services import wallet_service as ws
from app.services.boutique_service import own_boutique
from app.services.catalog_index import refresh_denormalized
from app.services.catalog_service import CatalogService, review_out
from app.services.media_service import MediaService
from app.services.studio_product_service import missing

S = OrderStatus
NOT_SALES = (S.CANCELLED.value, S.REFUNDED.value)
HELD = (
    S.PAID.value,
    S.PROCESSING.value,
    S.SHIPPED.value,
    S.DELIVERED.value,
    S.RETURN_REQUESTED.value,
)


def manila_day(ts: datetime) -> date:
    return as_aware(ts).astimezone(ws.MANILA).date()


# ─── Dashboard ─────────────────────────────────────────────────────────────


async def dashboard(session: AsyncSession, settings: Settings, user: User) -> Dashboard:
    assert_can(user, Permission.EARNINGS_VIEW)
    seller_id = own_boutique(user)
    profile = await session.get(SellerProfile, seller_id)
    assert profile is not None
    catalog = CatalogService(session, settings)
    now = utcnow()
    today = manila_day(now)
    since = now - timedelta(days=31)

    subs = list(
        (
            await session.scalars(
                select(SubOrder).where(
                    SubOrder.seller_id == seller_id, SubOrder.created_at >= since
                )
            )
        ).all()
    )
    sales = [s for s in subs if s.status not in NOT_SALES]
    per_day: dict[date, list[int]] = defaultdict(lambda: [0, 0])
    for s in sales:
        d = manila_day(s.created_at)
        per_day[d][0] += s.subtotal_qc
        per_day[d][1] += 1
    days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    series = [DayPoint(day=d, revenue_qc=per_day[d][0], orders=per_day[d][1]) for d in days]

    counts = dict(
        (
            await session.execute(
                select(SubOrder.status, func.count())
                .where(SubOrder.seller_id == seller_id)
                .group_by(SubOrder.status)
            )
        ).all()
    )
    total_orders = sum(n for st, n in counts.items() if st not in NOT_SALES)

    funnel_row = (
        await session.execute(
            select(
                func.coalesce(func.sum(Product.view_count), 0),
                func.coalesce(func.sum(Product.wishlist_count), 0),
                func.coalesce(func.sum(Product.bag_add_count), 0),
                func.count(Product.id),
            ).where(Product.seller_id == seller_id, Product.deleted_at.is_(None))
        )
    ).one()

    top_rows = (
        await session.execute(
            select(
                OrderItem.product_id,
                func.sum(OrderItem.qty),
                func.sum(OrderItem.line_total_qc),
            )
            .join(SubOrder, SubOrder.id == OrderItem.sub_order_id)
            .where(
                SubOrder.seller_id == seller_id,
                SubOrder.created_at >= since,
                SubOrder.status.notin_(NOT_SALES),
            )
            .group_by(OrderItem.product_id)
            .order_by(func.sum(OrderItem.line_total_qc).desc())
            .limit(5)
        )
    ).all()
    products = {
        p.id: p
        for p in (
            await session.scalars(select(Product).where(Product.id.in_([r[0] for r in top_rows])))
        ).all()
    }
    top = [
        TopProduct(
            id=pid,
            title=products[pid].title if pid in products else "Removed piece",
            image=catalog.abs_url(products[pid].images[0].url)
            if pid in products and products[pid].images
            else None,
            units=int(units or 0),
            revenue_qc=int(rev or 0),
        )
        for pid, units, rev in top_rows
    ]

    low = [
        LowStock(
            variant_id=v.id,
            product_id=p.id,
            title=p.title,
            options=v.options,
            stock=v.stock,
            threshold=v.low_stock_threshold,
        )
        for v, p in (
            await session.execute(
                select(Variant, Product)
                .join(Product, Product.id == Variant.product_id)
                .where(
                    Product.seller_id == seller_id,
                    Product.status == "active",
                    Product.deleted_at.is_(None),
                    Variant.stock <= Variant.low_stock_threshold,
                )
                .order_by(Variant.stock, Product.title)
                .limit(8)
            )
        ).all()
    ]

    todays = [s for s in sales if manila_day(s.created_at) == today]
    return Dashboard(
        boutique=profile.boutique_name,
        today_revenue_qc=sum(s.subtotal_qc for s in todays),
        today_orders=len(todays),
        to_fulfil=counts.get(S.PAID.value, 0) + counts.get(S.PROCESSING.value, 0),
        returns_open=counts.get(S.RETURN_REQUESTED.value, 0),
        revenue_30d_qc=sum(p.revenue_qc for p in series),
        series=series,
        funnel=Funnel(
            views=int(funnel_row[0]),
            wishlists=int(funnel_row[1]),
            bag_adds=int(funnel_row[2]),
            orders=total_orders,
        ),
        top_products=top,
        low_stock=low,
        # UX: Peak-End — the first sale is celebrated once, until dismissed.
        first_sale=total_orders > 0 and profile.first_sale_seen_at is None,
        product_count=int(funnel_row[3]),
    )


# ─── Earnings ──────────────────────────────────────────────────────────────


async def held_in_escrow(session: AsyncSession, seller_id: uuid.UUID) -> int:
    """What the boutique will receive (after 5%) for orders still in escrow."""
    return int(
        await session.scalar(
            select(func.coalesce(func.sum(SubOrder.subtotal_qc - SubOrder.commission_qc), 0)).where(
                SubOrder.seller_id == seller_id, SubOrder.status.in_(HELD)
            )
        )
        or 0
    )


async def earnings(session: AsyncSession, user: User) -> Earnings:
    assert_can(user, Permission.EARNINGS_VIEW)
    seller_id = own_boutique(user)
    wallet = await ws.user_wallet(session, user.id)
    released, commission = (
        await session.execute(
            select(
                func.coalesce(func.sum(SubOrder.subtotal_qc - SubOrder.commission_qc), 0),
                func.coalesce(func.sum(SubOrder.commission_qc), 0),
            ).where(SubOrder.seller_id == seller_id, SubOrder.status == S.COMPLETED.value)
        )
    ).one()
    payouts = (
        await session.execute(
            select(LedgerTransaction.reference, LedgerEntry.amount_qc, LedgerTransaction.created_at)
            .join(LedgerEntry, LedgerEntry.transaction_id == LedgerTransaction.id)
            .where(
                LedgerEntry.wallet_id == wallet.id,
                LedgerTransaction.type == TxType.WITHDRAWAL.value,
            )
            .order_by(LedgerTransaction.created_at.desc())
            .limit(50)
        )
    ).all()
    return Earnings(
        available_qc=wallet.balance_qc,
        in_escrow_qc=await held_in_escrow(session, seller_id),
        released_qc=int(released),
        commission_paid_qc=int(commission),
        withdrawn_qc=sum(-amt for _, amt, _ in payouts),
        payouts=[Payout(reference=ref, amount_qc=-amt, created_at=at) for ref, amt, at in payouts],
        has_pin=wallet.pin_hash is not None,
    )


# ─── Drops ─────────────────────────────────────────────────────────────────


def drop_state(d: Drop, now: datetime | None = None) -> str:
    now = now or utcnow()
    if as_aware(d.starts_at) > now:
        return "scheduled"
    if d.ends_at and as_aware(d.ends_at) <= now:
        return "ended"
    return "live"


async def drop_out(session: AsyncSession, settings: Settings, d: Drop) -> StudioDrop:
    subscribers = await session.scalar(
        select(func.count()).select_from(DropSubscription).where(DropSubscription.drop_id == d.id)
    )
    return StudioDrop(
        id=d.id,
        slug=d.slug,
        title=d.title,
        description=d.description,
        hero_url=CatalogService(session, settings).abs_url(d.hero_url),
        starts_at=d.starts_at,
        ends_at=d.ends_at,
        state=drop_state(d),  # type: ignore[arg-type]
        product_ids=[p.id for p in d.products],
        products=[p.title for p in d.products],
        subscribers=int(subscribers or 0),
    )


async def drops(session: AsyncSession, user: User) -> list[Drop]:
    assert_can(user, Permission.DROP_MANAGE)
    seller_id = own_boutique(user)
    return list(
        (
            await session.scalars(
                select(Drop).where(Drop.seller_id == seller_id).order_by(Drop.starts_at.desc())
            )
        ).all()
    )


async def _owned_drop(session: AsyncSession, user: User, drop_id: uuid.UUID) -> Drop:
    d = await session.get(Drop, drop_id)
    if d is None or d.seller_id != own_boutique(user):
        raise NotFound("We couldn't find that drop.", code="drop_not_found")
    return d


async def _drop_products(
    session: AsyncSession,
    seller_id: uuid.UUID,
    ids: list[uuid.UUID],
    exclude_drop: uuid.UUID | None,
) -> list[Product]:
    ids = list(dict.fromkeys(ids))
    products = list(
        (
            await session.scalars(
                select(Product).where(
                    Product.id.in_(ids),
                    Product.seller_id == seller_id,
                    Product.deleted_at.is_(None),
                    Product.status.in_(("draft", "active")),
                )
            )
        ).all()
    )
    if len(products) != len(ids):
        raise ValidationFailed("Pick your own draft or published pieces.", code="invalid_products")
    for p in products:
        variants = list(
            (await session.scalars(select(Variant).where(Variant.product_id == p.id))).all()
        )
        if problems := missing(p, variants):
            raise ValidationFailed(
                f"“{p.title}” isn't ready yet: {problems[0]}.", code="incomplete_product"
            )
    clash = await session.scalar(
        select(Product.title)
        .join(drop_products, drop_products.c.product_id == Product.id)
        .join(Drop, Drop.id == drop_products.c.drop_id)
        .where(
            Product.id.in_(ids),
            Drop.starts_at > utcnow(),
            *((Drop.id != exclude_drop,) if exclude_drop else ()),
        )
    )
    if clash:
        raise Conflict(f"“{clash}” is already in another upcoming drop.", code="product_in_drop")
    return products


def _on_sale(p: Product, now: datetime) -> bool:
    """Already public (published before now): a drop must not take it off sale."""
    return (
        p.status == "active" and p.published_at is not None and as_aware(p.published_at) <= now
    )


def _schedule(products: list[Product], starts_at: datetime, now: datetime) -> None:
    """New pieces publish when the drop starts (spec: real countdowns, no early
    peeks). Pieces already on sale stay on sale; the drop just features them."""
    for p in products:
        if not _on_sale(p, now):
            p.status = "active"
            p.published_at = starts_at


def _unschedule(products: list[Product], now: datetime) -> None:
    """Pieces leaving a drop go back to drafts only if they were never live."""
    for p in products:
        if not _on_sale(p, now):
            p.status, p.published_at = "draft", None


async def save_drop(
    session: AsyncSession,
    settings: Settings,
    user: User,
    body: DropIn,
    drop_id: uuid.UUID | None = None,
) -> Drop:
    assert_can(user, Permission.DROP_MANAGE)
    seller_id = own_boutique(user)
    now = utcnow()
    starts = as_aware(body.starts_at).astimezone(UTC)
    if starts < now + timedelta(minutes=5):
        raise ValidationFailed("Schedule the drop at least 5 minutes from now.", code="too_soon")
    d = await _owned_drop(session, user, drop_id) if drop_id else None
    if d is not None and drop_state(d, now) != "scheduled":
        raise Conflict("A drop can't be changed once it's live.", code="drop_started")
    products = await _drop_products(session, seller_id, body.product_ids, d.id if d else None)

    if d is None:
        base = slugify(body.title)[:100] or "drop"
        slug, n = base, 2
        while await session.scalar(select(Drop.id).where(Drop.slug == slug)):
            slug, n = f"{base}-{n}", n + 1
        d = Drop(seller_id=seller_id, slug=slug, title=body.title, starts_at=starts)
        session.add(d)
        await session.flush()
    else:
        # Pieces taken out of the drop go back to drafts (they were never live).
        _unschedule([p for p in d.products if p.id not in {x.id for x in products}], now)
        await session.execute(delete(drop_products).where(drop_products.c.drop_id == d.id))
    d.title = body.title
    d.description = (body.description or "").strip() or None
    d.starts_at = starts
    d.ends_at = as_aware(body.ends_at).astimezone(UTC) if body.ends_at else None
    if body.hero_asset_id:
        media = MediaService(session, settings)
        asset = await media.get_ready_asset(user, body.hero_asset_id, "product")
        d.hero_url = media.to_out(asset).url
    elif d.hero_url is None and products and products[0].images:
        d.hero_url = products[0].images[0].url
    await session.execute(
        insert(drop_products), [{"drop_id": d.id, "product_id": p.id} for p in products]
    )
    _schedule(products, starts, now)
    await session.commit()
    await session.refresh(d, ["products"])
    return d


async def delete_drop(session: AsyncSession, user: User, drop_id: uuid.UUID) -> None:
    assert_can(user, Permission.DROP_MANAGE)
    d = await _owned_drop(session, user, drop_id)
    if drop_state(d) != "scheduled":
        raise Conflict("Live or ended drops stay on record.", code="drop_started")
    _unschedule(list(d.products), utcnow())
    await session.delete(d)
    await session.commit()


async def notify_live_drops(session: AsyncSession, settings: Settings) -> int:
    """Scheduler job: tell "Notify me" subscribers once a drop goes live."""
    now = utcnow()
    due = list(
        (
            await session.scalars(
                select(Drop).where(Drop.notified_at.is_(None), Drop.starts_at <= now)
            )
        ).all()
    )
    sent = 0
    for d in due:
        subs = list(
            (
                await session.scalars(
                    select(DropSubscription).where(
                        DropSubscription.drop_id == d.id, DropSubscription.notified_at.is_(None)
                    )
                )
            ).all()
        )
        for sub in subs:
            member = await session.get(User, sub.user_id)
            if member is None:
                continue
            email = email_templates.order_update(
                template="drop_live",
                name=member.name,
                subject=f"{d.title} is live",
                heading="The drop is live.",
                body=f"{d.title} from {d.seller.boutique_name} just went live. "
                "Pieces are limited to real stock.",
                url=f"{settings.frontend_url}/drops",
                inbox_path="/drops",
                cta_label="See the drop",
            )
            email_service.queue(session, user=member, to_email=member.email, email=email)
            sub.notified_at = now
            sent += 1
        d.notified_at = now
        # Refresh denormalized stock so the drop's pieces list correctly.
        for p in d.products:
            refresh_denormalized(
                p,
                list(
                    (await session.scalars(select(Variant).where(Variant.product_id == p.id))).all()
                ),
            )
    await session.commit()
    return sent


# ─── Vouchers ──────────────────────────────────────────────────────────────


def voucher_state(v: Voucher, now: datetime | None = None) -> str:
    now = now or utcnow()
    if not v.is_active:
        return "paused"
    if v.used_count >= v.max_uses:
        return "used_up"
    if v.ends_at and as_aware(v.ends_at) <= now:
        return "expired"
    if v.starts_at and as_aware(v.starts_at) > now:
        return "scheduled"
    return "active"


async def vouchers(session: AsyncSession, user: User) -> list[StudioVoucher]:
    assert_can(user, Permission.VOUCHER_MANAGE)
    seller_id = own_boutique(user)
    rows = list(
        (
            await session.scalars(
                select(Voucher)
                .where(Voucher.seller_id == seller_id)
                .order_by(Voucher.created_at.desc())
            )
        ).all()
    )
    given = (
        dict(
            (
                await session.execute(
                    select(VoucherRedemption.voucher_id, func.sum(VoucherRedemption.discount_qc))
                    .where(VoucherRedemption.voucher_id.in_([v.id for v in rows]))
                    .group_by(VoucherRedemption.voucher_id)
                )
            ).all()
        )
        if rows
        else {}
    )
    return [voucher_out(v, int(given.get(v.id) or 0)) for v in rows]


def voucher_out(v: Voucher, given: int = 0) -> StudioVoucher:
    return StudioVoucher(
        id=v.id,
        code=v.code,
        type=v.type,
        value=v.value,
        min_spend_qc=v.min_spend_qc,
        max_uses=v.max_uses,
        used_count=v.used_count,
        starts_at=v.starts_at,
        ends_at=v.ends_at,
        is_active=v.is_active,
        description=v.description,
        state=voucher_state(v),  # type: ignore[arg-type]
        discount_given_qc=given,
    )


async def create_voucher(session: AsyncSession, user: User, body: VoucherIn) -> Voucher:
    assert_can(user, Permission.VOUCHER_MANAGE)
    seller_id = own_boutique(user)
    if await session.scalar(select(Voucher.id).where(Voucher.code == body.code)):
        raise Conflict("That code is taken. Try another.", code="voucher_code_taken")
    v = Voucher(
        seller_id=seller_id,
        code=body.code,
        type=body.type,
        value=body.value,
        min_spend_qc=body.min_spend_qc,
        max_uses=body.max_uses,
        used_count=0,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        is_active=True,
        description=(body.description or "").strip() or None,
    )
    session.add(v)
    await session.commit()
    await session.refresh(v)
    return v


async def _owned_voucher(session: AsyncSession, user: User, voucher_id: uuid.UUID) -> Voucher:
    assert_can(user, Permission.VOUCHER_MANAGE)
    v = await session.get(Voucher, voucher_id)
    if v is None or v.seller_id != own_boutique(user):
        raise NotFound("We couldn't find that voucher.", code="voucher_not_found")
    return v


async def update_voucher(
    session: AsyncSession, user: User, voucher_id: uuid.UUID, body: VoucherPatch
) -> Voucher:
    v = await _owned_voucher(session, user, voucher_id)
    data = body.model_dump(exclude_unset=True)
    if "max_uses" in data and body.max_uses is not None and body.max_uses < v.used_count:
        raise ValidationFailed(
            f"It has already been used {v.used_count} times.", code="max_uses_too_low"
        )
    if (
        "ends_at" in data
        and v.starts_at
        and body.ends_at
        and as_aware(body.ends_at) <= as_aware(v.starts_at)
    ):
        raise ValidationFailed("The voucher must end after it starts.", code="invalid_window")
    for field, value in data.items():
        setattr(v, field, (value.strip() or None) if isinstance(value, str) else value)
    await session.commit()
    await session.refresh(v)
    return v


async def delete_voucher(session: AsyncSession, user: User, voucher_id: uuid.UUID) -> None:
    v = await _owned_voucher(session, user, voucher_id)
    if v.used_count > 0:
        raise Conflict(
            "This voucher has been used, so it stays on record. Pause it instead.",
            code="voucher_used",
        )
    await session.delete(v)
    await session.commit()


# ─── Reviews ───────────────────────────────────────────────────────────────


async def reviews(session: AsyncSession, user: User, *, unreplied: bool) -> list[StudioReview]:
    assert_can(user, Permission.REVIEW_REPLY)
    seller_id = own_boutique(user)
    stmt = (
        select(Review, Product)
        .join(Product, Product.id == Review.product_id)
        .where(Product.seller_id == seller_id, Review.status == "published")
        .order_by(Review.created_at.desc())
        .limit(100)
    )
    if unreplied:
        stmt = stmt.where(Review.seller_reply.is_(None))
    return [
        StudioReview(
            **review_out(r).model_dump(),
            product_id=p.id,
            product_title=p.title,
            product_slug=p.slug,
        )
        for r, p in (await session.execute(stmt)).all()
    ]


async def reply(session: AsyncSession, user: User, review_id: uuid.UUID, text: str) -> Review:
    assert_can(user, Permission.REVIEW_REPLY)
    seller_id = own_boutique(user)
    row = (
        await session.execute(
            select(Review, Product)
            .join(Product, Product.id == Review.product_id)
            .where(Review.id == review_id)
        )
    ).first()
    if row is None or row[1].seller_id != seller_id:
        raise NotFound("We couldn't find that review.", code="review_not_found")
    review, product = row
    first_reply = review.seller_reply is None
    review.seller_reply = " ".join(text.split())
    review.seller_replied_at = utcnow()
    if first_reply:
        session.add(
            Notification(
                user_id=review.buyer_id,
                type="review.reply",
                payload={
                    "title": "The boutique replied to your review",
                    "body": f"About {product.title}: “{review.seller_reply[:120]}”",
                    "action_url": f"/p/{product.slug}",
                },
            )
        )
    await session.commit()
    await session.refresh(review)
    return review
