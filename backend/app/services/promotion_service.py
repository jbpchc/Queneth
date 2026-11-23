"""Promotions engine: admin campaigns, seller enrollment, scheduled price
changes and the public deals feed.

Prices change in one place (`_apply` / `_restore`), so the bag, vouchers and
checkout keep charging `Variant.price_qc` and need no promo logic of their own.
The original price becomes the compare-at ("was") price: a genuine markdown.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Permission, assert_can
from app.core.security import as_aware, utcnow
from app.core.text import slugify
from app.models.catalog import Product, Variant
from app.models.promotions import Promotion, PromotionEntry
from app.models.user import User
from app.schemas.catalog import ProductCard
from app.schemas.promotions import (
    DealsOut,
    EnrollIn,
    PromotionCard,
    PromotionDetail,
    PromotionIn,
    PromotionOut,
    SellerEntry,
    SellerPromotions,
)
from app.services import audit_service
from app.services.boutique_service import own_boutique
from app.services.catalog_index import refresh_denormalized
from app.services.catalog_service import CatalogService
from app.services.media_service import MediaService

OPEN_STATUSES = ("scheduled", "live")


def state(p: Promotion, now: datetime | None = None) -> str:
    now = now or utcnow()
    if not p.is_active:
        return "cancelled"
    if now < as_aware(p.starts_at):
        return "upcoming"
    if now < as_aware(p.ends_at):
        return "live"
    return "ended"


def sale_price(price_qc: int, percent: int) -> int:
    """Whole QC, rounded down in the shopper's favour, never below 1."""
    return max(1, price_qc * (100 - percent) // 100)


def promotion_out(p: Promotion, abs_url) -> PromotionOut:  # type: ignore[no-untyped-def]
    active = [e for e in p.entries if e.status in OPEN_STATUSES]
    return PromotionOut(
        id=p.id,
        slug=p.slug,
        title=p.title,
        badge=p.badge,
        description=p.description,
        hero_url=abs_url(p.hero_url),
        starts_at=p.starts_at,
        ends_at=p.ends_at,
        min_discount_percent=p.min_discount_percent,
        max_discount_percent=p.max_discount_percent,
        is_active=p.is_active,
        state=state(p),  # type: ignore[arg-type]
        product_count=len(active),
        seller_count=len({e.seller_id for e in active}),
    )


# ─── Prices ────────────────────────────────────────────────────────────────


async def _variants(
    session: AsyncSession, product_id: uuid.UUID, lock: bool = True
) -> list[Variant]:
    stmt = select(Variant).where(Variant.product_id == product_id).order_by(Variant.id)
    if lock:
        stmt = stmt.with_for_update()
    return list((await session.scalars(stmt)).all())


async def _refresh(session: AsyncSession, product_id: uuid.UUID) -> None:
    product = await session.get(Product, product_id)
    if product is not None:
        await session.flush()
        refresh_denormalized(product, await _variants(session, product_id, lock=False))


async def _apply(session: AsyncSession, entry: PromotionEntry, now: datetime) -> None:
    snapshot: dict[str, list[int | None]] = {}
    for v in await _variants(session, entry.product_id):
        snapshot[str(v.id)] = [v.price_qc, v.compare_at_qc]
        # Keep a higher genuine "was" price if the piece was already marked down.
        was = v.compare_at_qc if v.compare_at_qc and v.compare_at_qc > v.price_qc else v.price_qc
        v.price_qc = sale_price(v.price_qc, entry.discount_percent)
        v.compare_at_qc = was
    entry.original_prices = snapshot
    entry.status, entry.applied_at = "live", now
    await _refresh(session, entry.product_id)


async def _restore(
    session: AsyncSession, entry: PromotionEntry, status: str, now: datetime
) -> None:
    if entry.status == "live":
        for v in await _variants(session, entry.product_id):
            saved = entry.original_prices.get(str(v.id))
            if saved:
                v.price_qc, v.compare_at_qc = saved[0], saved[1]
        await _refresh(session, entry.product_id)
    entry.status, entry.ended_at = status, now


async def sweep(session: AsyncSession) -> dict[str, int]:
    """Scheduler job: start sales whose campaign went live, end the rest."""
    now = utcnow()
    counts = {"applied": 0, "restored": 0}
    entries = list(
        (
            await session.scalars(
                select(PromotionEntry).where(PromotionEntry.status.in_(OPEN_STATUSES))
            )
        ).all()
    )
    for e in entries:
        s = state(e.promotion, now)
        if e.status == "scheduled" and s == "live":
            await _apply(session, e, now)
            counts["applied"] += 1
        elif s in ("ended", "cancelled"):
            if e.status == "live":
                counts["restored"] += 1
            await _restore(session, e, "ended", now)
    await session.commit()
    return counts


# ─── Admin: campaigns ──────────────────────────────────────────────────────


async def list_all(session: AsyncSession, settings: Settings, admin: User) -> list[PromotionOut]:
    assert_can(admin, Permission.CATALOG_MANAGE)
    abs_url = CatalogService(session, settings).abs_url
    rows = (await session.scalars(select(Promotion).order_by(Promotion.starts_at.desc()))).all()
    return [promotion_out(p, abs_url) for p in rows]


async def save(
    session: AsyncSession,
    settings: Settings,
    admin: User,
    body: PromotionIn,
    promotion_id: uuid.UUID | None,
    ip: str | None,
) -> Promotion:
    assert_can(admin, Permission.CATALOG_MANAGE)
    if promotion_id:
        p = await session.get(Promotion, promotion_id)
        if p is None:
            raise NotFound("We couldn't find that promotion.", code="promotion_not_found")
        if not p.is_active:
            raise Conflict("This promotion was cancelled.", code="promotion_cancelled")
        # Pieces already enrolled must still fit a narrowed discount range.
        outside = [
            e
            for e in p.entries
            if e.status in OPEN_STATUSES
            and not body.min_discount_percent <= e.discount_percent <= body.max_discount_percent
        ]
        if outside:
            raise Conflict(
                f"{len(outside)} enrolled pieces are outside that discount range.",
                code="entries_outside_range",
            )
    else:
        base = slugify(body.title)[:100] or "promotion"
        slug, n = base, 2
        while await session.scalar(select(Promotion.id).where(Promotion.slug == slug)):
            slug, n = f"{base}-{n}", n + 1
        p = Promotion(slug=slug, created_by=admin.id, is_active=True)
        session.add(p)
    p.title, p.badge = body.title, body.badge
    p.description = (body.description or "").strip() or None
    p.starts_at, p.ends_at = body.starts_at, body.ends_at
    p.min_discount_percent, p.max_discount_percent = (
        body.min_discount_percent,
        body.max_discount_percent,
    )
    if body.hero_asset_id:
        media = MediaService(session, settings)
        asset = await media.get_ready_asset(admin, body.hero_asset_id, "product")
        p.hero_url = media.to_out(asset).url
    audit_service.record(
        session,
        actor_id=admin.id,
        action="promotion.save",
        target_type="promotion",
        target_id=p.slug,
        after=body.model_dump(mode="json", exclude={"hero_asset_id"}),
        ip=ip,
    )
    await session.commit()
    await sweep(session)  # dates may have moved a sale in or out of its window
    await session.refresh(p)
    return p


async def cancel(
    session: AsyncSession, admin: User, promotion_id: uuid.UUID, ip: str | None
) -> None:
    assert_can(admin, Permission.CATALOG_MANAGE)
    p = await session.get(Promotion, promotion_id)
    if p is None:
        raise NotFound("We couldn't find that promotion.", code="promotion_not_found")
    p.is_active = False
    audit_service.record(
        session, actor_id=admin.id, action="promotion.cancel", target_type="promotion",
        target_id=p.slug, ip=ip,
    )  # fmt: skip
    await session.commit()
    await sweep(session)  # restores every live price right away


# ─── Sellers: enrollment ───────────────────────────────────────────────────


async def for_seller(session: AsyncSession, settings: Settings, user: User) -> SellerPromotions:
    assert_can(user, Permission.PRODUCT_UPDATE)
    seller_id = own_boutique(user)
    catalog = CatalogService(session, settings)
    promos = (await session.scalars(select(Promotion).order_by(Promotion.starts_at))).all()
    open_ = [promotion_out(p, catalog.abs_url) for p in promos if state(p) in ("upcoming", "live")]
    rows = (
        await session.execute(
            select(PromotionEntry, Product)
            .join(Product, Product.id == PromotionEntry.product_id)
            .where(PromotionEntry.seller_id == seller_id)
            .order_by(PromotionEntry.created_at.desc())
        )
    ).all()
    entries = []
    for e, p in rows:
        # Before the sale, show what it will be; during it, the live price.
        base = p.min_price_qc
        if e.status == "live":
            sale, base = p.min_price_qc, p.compare_at_qc or p.min_price_qc
        else:
            sale = sale_price(base, e.discount_percent)
        entries.append(
            SellerEntry(
                id=e.id,
                promotion_id=e.promotion_id,
                promotion_title=e.promotion.title,
                promotion_state=state(e.promotion),  # type: ignore[arg-type]
                product_id=p.id,
                product_title=p.title,
                image=catalog.abs_url(p.images[0].url) if p.images else None,
                discount_percent=e.discount_percent,
                status=e.status,  # type: ignore[arg-type]
                price_qc=base,
                sale_price_qc=sale,
            )
        )
    return SellerPromotions(open=open_, entries=entries)


async def enroll(session: AsyncSession, user: User, promotion_id: uuid.UUID, body: EnrollIn) -> int:
    assert_can(user, Permission.PRODUCT_UPDATE)
    seller_id = own_boutique(user)
    promo = await session.get(Promotion, promotion_id)
    if promo is None or state(promo) not in ("upcoming", "live"):
        raise NotFound("That promotion isn't open for entries.", code="promotion_not_open")
    if not promo.min_discount_percent <= body.discount_percent <= promo.max_discount_percent:
        raise ValidationFailed(
            f"{promo.title} takes discounts from {promo.min_discount_percent}% "
            f"to {promo.max_discount_percent}%.",
            code="discount_out_of_range",
        )
    ids = list(dict.fromkeys(body.product_ids))
    products = list(
        (
            await session.scalars(
                select(Product).where(
                    Product.id.in_(ids),
                    Product.seller_id == seller_id,
                    Product.status == "active",
                    Product.deleted_at.is_(None),
                )
            )
        ).all()
    )
    if len(products) != len(ids):
        raise ValidationFailed("Pick your own published pieces.", code="invalid_products")
    # One sale at a time per piece: no stacking overlapping campaigns.
    busy = (
        await session.execute(
            select(Product.title)
            .join(PromotionEntry, PromotionEntry.product_id == Product.id)
            .join(Promotion, Promotion.id == PromotionEntry.promotion_id)
            .where(
                Product.id.in_(ids),
                PromotionEntry.status.in_(OPEN_STATUSES),
                PromotionEntry.promotion_id != promo.id,
                Promotion.is_active.is_(True),
                Promotion.starts_at < promo.ends_at,
                Promotion.ends_at > promo.starts_at,
            )
        )
    ).first()
    if busy:
        raise Conflict(
            f"“{busy[0]}” is already in another sale at that time.", code="already_on_sale"
        )
    now = utcnow()
    live = state(promo, now) == "live"
    existing = {
        e.product_id: e
        for e in (
            await session.scalars(
                select(PromotionEntry).where(
                    PromotionEntry.promotion_id == promo.id, PromotionEntry.product_id.in_(ids)
                )
            )
        ).all()
    }
    for p in products:
        e = existing.get(p.id)
        if e is not None and e.status == "live":
            if e.discount_percent != body.discount_percent:
                # Change the discount on a live sale: restore, then re-apply.
                await _restore(session, e, "scheduled", now)
                e.discount_percent = body.discount_percent
                await _apply(session, e, now)
            continue
        if e is None:
            e = PromotionEntry(promotion_id=promo.id, product_id=p.id, seller_id=seller_id)
            e.promotion = promo
            session.add(e)
        e.discount_percent, e.status, e.ended_at = body.discount_percent, "scheduled", None
        await session.flush()
        if live:
            await _apply(session, e, now)
    await session.commit()
    return len(products)


async def withdraw(session: AsyncSession, user: User, entry_id: uuid.UUID) -> None:
    assert_can(user, Permission.PRODUCT_UPDATE)
    e = await session.get(PromotionEntry, entry_id)
    if e is None or e.seller_id != own_boutique(user):
        raise NotFound("We couldn't find that entry.", code="entry_not_found")
    if e.status in OPEN_STATUSES:
        await _restore(session, e, "withdrawn", utcnow())
    await session.commit()


async def live_entry(session: AsyncSession, product_id: uuid.UUID) -> PromotionEntry | None:
    return await session.scalar(
        select(PromotionEntry).where(
            PromotionEntry.product_id == product_id, PromotionEntry.status == "live"
        )
    )


# ─── Shoppers: deals ───────────────────────────────────────────────────────


async def _live_cards(
    session: AsyncSession, catalog: CatalogService, promo: Promotion, visible: dict
) -> list[ProductCard]:  # type: ignore[type-arg]
    live_drop = await catalog.live_drop_product_ids()
    picks = sorted(
        (e for e in promo.entries if e.status == "live" and e.product_id in visible),
        key=lambda e: (-e.discount_percent, -visible[e.product_id].wishlist_count),
    )
    return [catalog.card(visible[e.product_id], live_drop) for e in picks]


async def _card(
    session: AsyncSession, catalog: CatalogService, p: Promotion, visible: dict, preview: int
) -> tuple[PromotionCard, list[ProductCard]]:  # type: ignore[type-arg]
    cards = await _live_cards(session, catalog, p, visible)
    live = [e for e in p.entries if e.status == "live" and e.product_id in visible]
    out = promotion_out(p, catalog.abs_url)
    return (
        PromotionCard(
            **out.model_dump(),
            preview=cards[:preview],
            top_discount_percent=max((e.discount_percent for e in live), default=0),
        ),
        cards,
    )


async def deals(session: AsyncSession, settings: Settings, limit: int = 24) -> DealsOut:
    catalog = CatalogService(session, settings)
    products = await catalog.visible_products()
    visible = {p.id: p for p in products}
    promos = (await session.scalars(select(Promotion).where(Promotion.is_active.is_(True)))).all()
    cards = []
    for p in sorted(promos, key=lambda x: as_aware(x.ends_at)):
        if state(p) != "live":
            continue
        card, all_cards = await _card(session, catalog, p, visible, preview=8)
        if all_cards:  # a campaign with nothing on sale yet isn't shown to shoppers
            cards.append(card)
    marked = sorted(
        (
            p
            for p in products
            if p.compare_at_qc and p.compare_at_qc > p.min_price_qc and p.total_stock > 0
        ),
        key=lambda p: (-(p.compare_at_qc - p.min_price_qc) / p.compare_at_qc, p.slug),  # type: ignore[operator]
    )
    live_drop = await catalog.live_drop_product_ids()
    return DealsOut(promotions=cards, on_sale=[catalog.card(p, live_drop) for p in marked[:limit]])


async def detail(session: AsyncSession, settings: Settings, slug: str) -> PromotionDetail:
    catalog = CatalogService(session, settings)
    p = await session.scalar(select(Promotion).where(Promotion.slug == slug))
    if p is None or state(p) in ("cancelled", "ended"):
        raise NotFound("That promotion isn't running.", code="promotion_not_found")
    visible = {x.id: x for x in await catalog.visible_products()}
    card, cards = await _card(session, catalog, p, visible, preview=8)
    return PromotionDetail(**card.model_dump(), products=cards)


async def counts(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(PromotionEntry).where(PromotionEntry.status == "live")
        )
        or 0
    )
