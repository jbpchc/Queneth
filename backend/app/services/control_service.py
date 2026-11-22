"""Admin Control Room (Phase 9): overview, seller directory, user search,
catalog management, featured slots and moderation. Every mutation is
permission-checked and audit-logged."""

import uuid
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Permission, assert_can
from app.core.security import utcnow
from app.core.text import slugify
from app.models.catalog import Category, Collection, Product, Review, SellerProfile, Subcategory
from app.models.commerce import Order, OrderItem, OrderStatus, SubOrder
from app.models.integration import ContentFlag, Notification
from app.models.user import AuditLog, User
from app.models.wallet import SystemWallet, Wallet
from app.schemas.control import (
    AdminCategory,
    AdminCollection,
    AdminSeller,
    AdminSubcategory,
    AdminUserDetail,
    AdminUserRow,
    Boutique,
    CategoryPatch,
    CategoryShare,
    CollectionIn,
    FlagGroup,
    Overview,
    Owner,
    PickRow,
    ReportIn,
    SubcategoryPatch,
    TagOption,
)
from app.schemas.studio import DayPoint
from app.services import audit_service, review_service, user_service
from app.services.catalog_service import CatalogService
from app.services.media_service import MediaService
from app.services.studio_service import manila_day

S = OrderStatus
NOT_SALES = (S.CANCELLED.value, S.REFUNDED.value)


# ─── Overview ──────────────────────────────────────────────────────────────


async def overview(session: AsyncSession, admin: User) -> Overview:
    assert_can(admin, Permission.ANALYTICS_VIEW)
    now = utcnow()
    since = now - timedelta(days=30)
    sales = SubOrder.status.notin_(NOT_SALES)

    gmv, orders = (
        await session.execute(
            select(
                func.coalesce(func.sum(SubOrder.subtotal_qc), 0),
                func.count(distinct(SubOrder.order_id)),
            ).where(sales)
        )
    ).one()
    recent = list(
        (
            await session.execute(
                select(SubOrder.created_at, SubOrder.subtotal_qc, SubOrder.order_id).where(
                    sales, SubOrder.created_at >= since
                )
            )
        ).all()
    )
    per_day: dict[date, list[Any]] = defaultdict(lambda: [0, set()])
    for created, subtotal, oid in recent:
        d = manila_day(created)
        per_day[d][0] += subtotal
        per_day[d][1].add(oid)
    today = manila_day(now)
    days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    series = [DayPoint(day=d, revenue_qc=per_day[d][0], orders=len(per_day[d][1])) for d in days]

    active_buyers = await session.scalar(
        select(func.count(distinct(Order.buyer_id))).where(Order.created_at >= since)
    )
    users_total = await session.scalar(select(func.count()).select_from(User))
    seller_counts = dict(
        (
            await session.execute(
                select(SellerProfile.status, func.count()).group_by(SellerProfile.status)
            )
        ).all()
    )
    wallets = dict(
        (
            await session.execute(
                select(Wallet.system_code, Wallet.balance_qc).where(Wallet.system_code.is_not(None))
            )
        ).all()
    )
    top = (
        await session.execute(
            select(
                Category.slug,
                Category.name,
                func.sum(OrderItem.line_total_qc),
                func.sum(OrderItem.qty),
            )
            .join(Product, Product.category_id == Category.id)
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(SubOrder, SubOrder.id == OrderItem.sub_order_id)
            .where(sales)
            .group_by(Category.slug, Category.name)
            .order_by(func.sum(OrderItem.line_total_qc).desc())
        )
    ).all()
    open_reports = await session.scalar(
        select(func.count(distinct(ContentFlag.target_id))).where(ContentFlag.status == "open")
    )
    return Overview(
        gmv_qc=int(gmv),
        gmv_30d_qc=sum(p.revenue_qc for p in series),
        orders=int(orders),
        orders_30d=len({oid for _, _, oid in recent}),
        users_total=int(users_total or 0),
        active_buyers_30d=int(active_buyers or 0),
        sellers_active=seller_counts.get("approved", 0),
        sellers_pending=seller_counts.get("pending", 0),
        escrow_qc=wallets.get(SystemWallet.ESCROW.value, 0),
        platform_revenue_qc=wallets.get(SystemWallet.PLATFORM_REVENUE.value, 0),
        open_reports=int(open_reports or 0),
        series=series,
        top_categories=[
            CategoryShare(slug=slug, name=name, revenue_qc=int(rev or 0), units=int(units or 0))
            for slug, name, rev, units in top
        ],
    )


# ─── Sellers ───────────────────────────────────────────────────────────────


async def sellers(
    session: AsyncSession, settings: Settings, admin: User, *, status: str | None, q: str | None
) -> tuple[list[AdminSeller], dict[str, int]]:
    assert_can(admin, Permission.SELLER_APPROVE)
    stmt = select(SellerProfile, User).join(User, User.id == SellerProfile.user_id)
    if status:
        stmt = stmt.where(SellerProfile.status == status)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(SellerProfile.boutique_name).like(like),
                func.lower(User.email).like(like),
            )
        )
    rows = (await session.execute(stmt.order_by(SellerProfile.created_at.desc()))).all()
    ids = [p.id for p, _ in rows]
    products = (
        dict(
            (
                await session.execute(
                    select(Product.seller_id, func.count())
                    .where(Product.seller_id.in_(ids), Product.deleted_at.is_(None))
                    .group_by(Product.seller_id)
                )
            ).all()
        )
        if ids
        else {}
    )
    sales = (
        {
            sid: (n, total)
            for sid, n, total in (
                await session.execute(
                    select(
                        SubOrder.seller_id,
                        func.count(),
                        func.coalesce(func.sum(SubOrder.subtotal_qc), 0),
                    )
                    .where(SubOrder.seller_id.in_(ids), SubOrder.status.notin_(NOT_SALES))
                    .group_by(SubOrder.seller_id)
                )
            ).all()
        }
        if ids
        else {}
    )
    counts = dict(
        (
            await session.execute(
                select(SellerProfile.status, func.count()).group_by(SellerProfile.status)
            )
        ).all()
    )
    abs_url = CatalogService(session, settings).abs_url
    out = [
        AdminSeller(
            id=p.id,
            boutique_name=p.boutique_name,
            slug=p.slug,
            status=p.status,  # type: ignore[arg-type]
            owner=Owner(id=u.id, name=u.name, email=u.email),
            city=p.city,
            tagline=p.tagline,
            bio=p.bio,
            logo_url=abs_url(p.logo_url),
            product_count=int(products.get(p.id, 0)),
            orders=int(sales.get(p.id, (0, 0))[0]),
            gmv_qc=int(sales.get(p.id, (0, 0))[1]),
            follower_count=p.follower_count,
            is_featured=p.is_featured,
            rejection_reason=p.rejection_reason,
            created_at=p.created_at,
            approved_at=p.approved_at,
        )
        for p, u in rows
    ]
    return out, {str(k): int(v) for k, v in counts.items()}


async def set_suspended(
    session: AsyncSession,
    admin: User,
    seller_id: uuid.UUID,
    suspend: bool,
    reason: str | None,
    ip: str | None,
) -> SellerProfile:
    """Suspending hides the boutique and its pieces and closes its Studio;
    open orders keep their escrow and can still be fulfilled or refunded by admins."""
    assert_can(admin, Permission.SELLER_APPROVE)
    profile = await session.get(SellerProfile, seller_id)
    if profile is None:
        raise NotFound("We couldn't find that boutique.", code="boutique_not_found")
    if suspend and profile.status != "approved":
        raise Conflict("Only approved boutiques can be suspended.", code="not_approved")
    if not suspend and profile.status != "suspended":
        raise Conflict("This boutique isn't suspended.", code="not_suspended")
    if suspend and not (reason or "").strip():
        raise ValidationFailed("Give a reason for the suspension.", code="reason_required")
    before = profile.status
    profile.status = "suspended" if suspend else "approved"
    owner_title = "Your boutique is suspended" if suspend else "Your boutique is back"
    owner_body = (
        f"{profile.boutique_name} is hidden from shoppers: {reason}. "
        "Reply to this notice to appeal."
        if suspend
        else f"{profile.boutique_name} is visible to shoppers again."
    )
    session.add(
        Notification(
            user_id=profile.user_id,
            type="seller.status",
            payload={"title": owner_title, "body": owner_body, "action_url": "/account"},
        )
    )
    audit_service.record(
        session,
        actor_id=admin.id,
        action="seller.suspend" if suspend else "seller.reinstate",
        target_type="seller_profile",
        target_id=profile.id,
        before={"status": before},
        after={"status": profile.status},
        reason=reason,
        ip=ip,
    )
    await session.commit()
    return profile


async def set_boutique_featured(
    session: AsyncSession, admin: User, seller_id: uuid.UUID, on: bool, ip: str | None
) -> None:
    assert_can(admin, Permission.CATALOG_MANAGE)
    profile = await session.get(SellerProfile, seller_id)
    if profile is None:
        raise NotFound("We couldn't find that boutique.", code="boutique_not_found")
    if on and profile.status != "approved":
        raise Conflict("Only approved boutiques can be featured.", code="not_approved")
    profile.is_featured = on
    audit_service.record(
        session,
        actor_id=admin.id,
        action="boutique.featured",
        target_type="seller_profile",
        target_id=profile.id,
        after={"is_featured": on},
        ip=ip,
    )
    await session.commit()


# ─── Users ─────────────────────────────────────────────────────────────────


async def _user_rows(session: AsyncSession, users: list[User]) -> list[AdminUserRow]:
    ids = [u.id for u in users]
    if not ids:
        return []
    orders = dict(
        (
            await session.execute(
                select(Order.buyer_id, func.count())
                .where(Order.buyer_id.in_(ids))
                .group_by(Order.buyer_id)
            )
        ).all()
    )
    wallets = dict(
        (
            await session.execute(
                select(Wallet.user_id, Wallet.balance_qc).where(Wallet.user_id.in_(ids))
            )
        ).all()
    )
    out = []
    for u in users:
        me = user_service.to_me(u)
        p = u.seller_profile
        out.append(
            AdminUserRow(
                **me.model_dump(exclude={"permissions"}),
                last_login_at=u.last_login_at,
                orders=int(orders.get(u.id, 0)),
                wallet_qc=int(wallets.get(u.id, 0)),
                boutique=Boutique(name=p.boutique_name, slug=p.slug, status=p.status)
                if p
                else None,
            )
        )
    return out


async def users(
    session: AsyncSession,
    admin: User,
    *,
    q: str | None,
    role: str | None,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[AdminUserRow], int]:
    assert_can(admin, Permission.USER_VIEW)
    stmt = select(User)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.name).like(like)))
    if status:
        stmt = stmt.where(User.status == status)
    rows = list((await session.scalars(stmt.order_by(User.created_at.desc()))).all())
    if role:
        rows = [u for u in rows if role in (u.roles or [])]  # roles are an array column
    total = len(rows)
    return await _user_rows(session, rows[offset : offset + limit]), total


async def user_detail(session: AsyncSession, admin: User, user_id: uuid.UUID) -> AdminUserDetail:
    assert_can(admin, Permission.USER_VIEW)
    u = await session.get(User, user_id)
    if u is None:
        raise NotFound("We couldn't find that user.", code="user_not_found")
    [row] = await _user_rows(session, [u])
    spent = await session.scalar(
        select(func.coalesce(func.sum(SubOrder.subtotal_qc), 0))
        .join(Order, Order.id == SubOrder.order_id)
        .where(Order.buyer_id == u.id, SubOrder.status.notin_(NOT_SALES))
    )
    reviews = await session.scalar(
        select(func.count()).select_from(Review).where(Review.buyer_id == u.id)
    )
    reports = await session.scalar(
        select(func.count()).select_from(ContentFlag).where(ContentFlag.reporter_id == u.id)
    )
    audit = (
        await session.scalars(
            select(AuditLog)
            .where(or_(AuditLog.target_id == str(u.id), AuditLog.actor_id == u.id))
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        )
    ).all()
    return AdminUserDetail(
        **row.model_dump(),
        spent_qc=int(spent or 0),
        reviews=int(reviews or 0),
        reports_made=int(reports or 0),
        recent_audit=[
            {
                "action": a.action,
                "reason": a.reason,
                "created_at": a.created_at.isoformat(),
                "after": a.after,
            }
            for a in audit
        ],
    )


# ─── Catalog ───────────────────────────────────────────────────────────────


async def categories(session: AsyncSession, admin: User) -> list[AdminCategory]:
    assert_can(admin, Permission.CATALOG_MANAGE)
    cats = (await session.scalars(select(Category).order_by(Category.sort_order))).all()
    subs = (
        await session.scalars(
            select(Subcategory).order_by(Subcategory.sort_order, Subcategory.name)
        )
    ).all()
    live = and_(Product.deleted_at.is_(None), Product.status == "active")
    per_cat = dict(
        (
            await session.execute(
                select(Product.category_id, func.count()).where(live).group_by(Product.category_id)
            )
        ).all()
    )
    per_sub = dict(
        (
            await session.execute(
                select(Product.subcategory_id, func.count())
                .where(live)
                .group_by(Product.subcategory_id)
            )
        ).all()
    )
    return [
        AdminCategory(
            id=c.id,
            slug=c.slug,
            name=c.name,
            tagline=c.tagline,
            sort_order=c.sort_order,
            product_count=int(per_cat.get(c.id, 0)),
            attribute_schema=c.attribute_schema or {},
            subcategories=[
                AdminSubcategory(
                    id=s.id,
                    slug=s.slug,
                    name=s.name,
                    sort_order=s.sort_order,
                    product_count=int(per_sub.get(s.id, 0)),
                )
                for s in subs
                if s.category_id == c.id
            ],
        )
        for c in cats
    ]


async def update_category(
    session: AsyncSession, admin: User, category_id: uuid.UUID, body: CategoryPatch, ip: str | None
) -> None:
    assert_can(admin, Permission.CATALOG_MANAGE)
    c = await session.get(Category, category_id)
    if c is None:
        raise NotFound("We couldn't find that category.", code="category_not_found")
    data = body.model_dump(exclude_unset=True)
    before = {k: getattr(c, k) for k in data}
    for k, v in data.items():
        setattr(c, k, (" ".join(v.split()) or None) if isinstance(v, str) else v)
    audit_service.record(
        session,
        actor_id=admin.id,
        action="catalog.category",
        target_type="category",
        target_id=c.id,
        before=before,
        after=data,
        ip=ip,
    )
    await session.commit()


async def create_subcategory(
    session: AsyncSession, admin: User, category_id: uuid.UUID, name: str, ip: str | None
) -> Subcategory:
    assert_can(admin, Permission.CATALOG_MANAGE)
    c = await session.get(Category, category_id)
    if c is None:
        raise NotFound("We couldn't find that category.", code="category_not_found")
    slug = slugify(name)
    if await session.scalar(
        select(Subcategory.id).where(Subcategory.category_id == c.id, Subcategory.slug == slug)
    ):
        raise Conflict(f"{c.name} already has “{name}”.", code="subcategory_exists")
    top = await session.scalar(
        select(func.max(Subcategory.sort_order)).where(Subcategory.category_id == c.id)
    )
    sub = Subcategory(category_id=c.id, name=name, slug=slug, sort_order=(top or 0) + 1)
    session.add(sub)
    audit_service.record(
        session,
        actor_id=admin.id,
        action="catalog.subcategory.create",
        target_type="category",
        target_id=c.id,
        after={"name": name},
        ip=ip,
    )
    await session.commit()
    return sub


async def update_subcategory(
    session: AsyncSession, admin: User, sub_id: uuid.UUID, body: SubcategoryPatch, ip: str | None
) -> None:
    """Renaming keeps the slug, so existing links keep working."""
    assert_can(admin, Permission.CATALOG_MANAGE)
    sub = await session.get(Subcategory, sub_id)
    if sub is None:
        raise NotFound("We couldn't find that subcategory.", code="subcategory_not_found")
    data = body.model_dump(exclude_unset=True)
    if body.name is not None:
        sub.name = " ".join(body.name.split())
    if body.sort_order is not None:
        sub.sort_order = body.sort_order
    audit_service.record(
        session,
        actor_id=admin.id,
        action="catalog.subcategory.update",
        target_type="subcategory",
        target_id=sub.id,
        after=data,
        ip=ip,
    )
    await session.commit()


async def delete_subcategory(
    session: AsyncSession, admin: User, sub_id: uuid.UUID, ip: str | None
) -> None:
    assert_can(admin, Permission.CATALOG_MANAGE)
    sub = await session.get(Subcategory, sub_id)
    if sub is None:
        raise NotFound("We couldn't find that subcategory.", code="subcategory_not_found")
    used = await session.scalar(
        select(func.count()).select_from(Product).where(Product.subcategory_id == sub.id)
    )
    if used:
        raise Conflict(
            f"{used} products use “{sub.name}”. Move them first.", code="subcategory_in_use"
        )
    await session.delete(sub)
    audit_service.record(
        session,
        actor_id=admin.id,
        action="catalog.subcategory.delete",
        target_type="subcategory",
        target_id=sub_id,
        before={"name": sub.name},
        ip=ip,
    )
    await session.commit()


async def picks(
    session: AsyncSession, settings: Settings, admin: User, sub_id: uuid.UUID
) -> list[PickRow]:
    assert_can(admin, Permission.CATALOG_MANAGE)
    catalog = CatalogService(session, settings)
    rows = (
        await session.scalars(
            select(Product)
            .where(
                Product.subcategory_id == sub_id,
                Product.status == "active",
                Product.deleted_at.is_(None),
            )
            .order_by(Product.is_connoisseur_pick.desc(), Product.curated_score.desc())
        )
    ).all()
    return [
        PickRow(
            id=p.id,
            title=p.title,
            slug=p.slug,
            boutique=p.seller.boutique_name,
            image=catalog.abs_url(p.images[0].url) if p.images else None,
            price_qc=p.min_price_qc,
            is_pick=p.is_connoisseur_pick,
        )
        for p in rows
    ]


async def set_pick(
    session: AsyncSession, admin: User, product_id: uuid.UUID, on: bool, ip: str | None
) -> None:
    """One Connoisseur's pick per subcategory: choosing one clears the others."""
    assert_can(admin, Permission.CATALOG_MANAGE)
    p = await session.get(Product, product_id)
    if p is None or p.deleted_at is not None:
        raise NotFound("We couldn't find that product.", code="product_not_found")
    if on:
        if p.status != "active":
            raise Conflict("Only live pieces can be picked.", code="not_live")
        others = await session.scalars(
            select(Product).where(
                Product.subcategory_id == p.subcategory_id,
                Product.is_connoisseur_pick,
                Product.id != p.id,
            )
        )
        for o in others.all():
            o.is_connoisseur_pick = False
    p.is_connoisseur_pick = on
    audit_service.record(
        session,
        actor_id=admin.id,
        action="catalog.pick",
        target_type="product",
        target_id=p.id,
        after={"is_connoisseur_pick": on},
        ip=ip,
    )
    await session.commit()


async def _tag_counts(session: AsyncSession) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for tags in (
        await session.scalars(
            select(Product.tags).where(Product.status == "active", Product.deleted_at.is_(None))
        )
    ).all():
        for t in tags or []:
            counts[t] += 1
    return counts


async def collections(
    session: AsyncSession, settings: Settings, admin: User
) -> tuple[list[AdminCollection], list[TagOption]]:
    assert_can(admin, Permission.CATALOG_MANAGE)
    abs_url = CatalogService(session, settings).abs_url
    counts = await _tag_counts(session)
    rows = (
        await session.scalars(select(Collection).order_by(Collection.sort_order, Collection.title))
    ).all()
    return (
        [collection_out(c, counts.get(c.tag, 0), abs_url) for c in rows],
        [TagOption(tag=t, products=n) for t, n in sorted(counts.items(), key=lambda kv: -kv[1])],
    )


def collection_out(c: Collection, count: int, abs_url) -> AdminCollection:  # type: ignore[no-untyped-def]
    return AdminCollection(
        id=c.id,
        slug=c.slug,
        title=c.title,
        kicker=c.kicker,
        subtitle=c.subtitle,
        body=c.body,
        tag=c.tag,
        hero_url=abs_url(c.hero_url),
        is_featured=c.is_featured,
        sort_order=c.sort_order,
        product_count=count,
    )


async def save_collection(
    session: AsyncSession,
    settings: Settings,
    admin: User,
    body: CollectionIn,
    collection_id: uuid.UUID | None,
    ip: str | None,
) -> Collection:
    assert_can(admin, Permission.CATALOG_MANAGE)
    if collection_id:
        c = await session.get(Collection, collection_id)
        if c is None:
            raise NotFound("We couldn't find that collection.", code="collection_not_found")
    else:
        base = slugify(body.title)[:100] or "collection"
        slug, n = base, 2
        while await session.scalar(select(Collection.id).where(Collection.slug == slug)):
            slug, n = f"{base}-{n}", n + 1
        c = Collection(slug=slug)
        session.add(c)
    c.title = " ".join(body.title.split())
    c.kicker = body.kicker or None
    c.subtitle = body.subtitle or None
    c.body = body.body or None
    c.tag = body.tag
    c.is_featured = body.is_featured
    c.sort_order = body.sort_order
    if body.hero_asset_id:
        media = MediaService(session, settings)
        asset = await media.get_ready_asset(admin, body.hero_asset_id, "product")
        c.hero_url = media.to_out(asset).url
    audit_service.record(
        session,
        actor_id=admin.id,
        action="catalog.collection.save",
        target_type="collection",
        target_id=c.slug,
        after=body.model_dump(mode="json", exclude={"hero_asset_id"}),
        ip=ip,
    )
    await session.commit()
    await session.refresh(c)
    return c


async def delete_collection(
    session: AsyncSession, admin: User, collection_id: uuid.UUID, ip: str | None
) -> None:
    assert_can(admin, Permission.CATALOG_MANAGE)
    c = await session.get(Collection, collection_id)
    if c is None:
        raise NotFound("We couldn't find that collection.", code="collection_not_found")
    await session.delete(c)
    audit_service.record(
        session,
        actor_id=admin.id,
        action="catalog.collection.delete",
        target_type="collection",
        target_id=c.slug,
        ip=ip,
    )
    await session.commit()


# ─── Reports (shoppers) & moderation (admins) ──────────────────────────────


async def report(session: AsyncSession, user: User, body: ReportIn) -> None:
    assert_can(user, Permission.PROFILE_MANAGE)
    if body.target_type == "product":
        p = await session.get(Product, body.target_id)
        if p is None or p.deleted_at is not None or p.status != "active":
            raise NotFound("We couldn't find that piece.", code="product_not_found")
        if user.seller_id is not None and p.seller_id == user.seller_id:
            raise Conflict("You can't report your own piece.", code="own_content")
    else:
        r = await session.get(Review, body.target_id)
        if r is None or r.status != "published":
            raise NotFound("We couldn't find that review.", code="review_not_found")
        if r.buyer_id == user.id:
            raise Conflict("You can't report your own review.", code="own_content")
    session.add(
        ContentFlag(
            target_type=body.target_type,
            target_id=body.target_id,
            reporter_id=user.id,
            reason=body.reason,
            note=" ".join((body.note or "").split()) or None,
            status="open",
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()  # already reported and still open: fine, nothing to do


async def flags(
    session: AsyncSession, settings: Settings, admin: User, *, status: str
) -> list[FlagGroup]:
    assert_can(admin, Permission.REVIEW_MODERATE)
    catalog = CatalogService(session, settings)
    rows = list(
        (
            await session.scalars(
                select(ContentFlag)
                .where(ContentFlag.status == status)
                .order_by(ContentFlag.created_at)
            )
        ).all()
    )
    grouped: dict[tuple[str, uuid.UUID], list[ContentFlag]] = defaultdict(list)
    for f in rows:
        grouped[(f.target_type, f.target_id)].append(f)
    out: list[FlagGroup] = []
    for (kind, tid), fs in grouped.items():
        reasons: dict[str, int] = defaultdict(int)
        for f in fs:
            reasons[f.reason] += 1
        common = {
            "target_type": kind,
            "target_id": tid,
            "reports": len(fs),
            "reasons": dict(reasons),
            "notes": [f.note for f in fs if f.note][:5],
            "first_reported_at": fs[0].created_at,
            "last_reported_at": fs[-1].created_at,
            "status": status,
            "resolution": fs[-1].resolution,
        }
        if kind == "product":
            p = await session.get(Product, tid)
            if p is None:
                continue
            out.append(
                FlagGroup(
                    **common,
                    title=p.title,
                    subtitle=p.seller.boutique_name,
                    excerpt=(p.description or "")[:200] or None,
                    url=f"/p/{p.slug}",
                    image=catalog.abs_url(p.images[0].url) if p.images else None,
                    content_status=p.status,
                )
            )
        else:
            r = await session.get(Review, tid)
            if r is None:
                continue
            p = await session.get(Product, r.product_id)
            out.append(
                FlagGroup(
                    **common,
                    title=r.title or f"{r.rating}★ review",
                    subtitle=(
                        f"{r.buyer.name if r.buyer else 'A shopper'} "
                        f"on {p.title if p else 'a piece'}"
                    ),
                    excerpt=r.body[:300],
                    url=f"/p/{p.slug}#reviews" if p else None,
                    image=None,
                    content_status=r.status,
                )
            )
    # Most-reported first (UX: Serial Position — what matters most leads).
    out.sort(key=lambda g: (-g.reports, g.first_reported_at))
    return out


async def moderate(
    session: AsyncSession,
    admin: User,
    target_type: str,
    target_id: uuid.UUID,
    action: str,
    note: str | None,
    ip: str | None,
) -> None:
    assert_can(admin, Permission.REVIEW_MODERATE)
    now = utcnow()
    if target_type == "review":
        r = await session.get(Review, target_id)
        if r is None:
            raise NotFound("We couldn't find that review.", code="review_not_found")
        if action in ("hide", "remove"):
            r.status = "hidden"
        elif action == "restore":
            r.status = "published"
        before = None
        await session.flush()
        await review_service.refresh_rating(session, r.product_id)
        if action in ("hide", "remove"):
            session.add(
                Notification(
                    user_id=r.buyer_id,
                    type="moderation.review",
                    payload={
                        "title": "Your review was hidden",
                        "body": note or "It didn't meet our community guidelines.",
                        "action_url": "/account/orders",
                    },
                )
            )
    elif target_type == "product":
        assert_can(admin, Permission.PRODUCT_ARCHIVE)
        p = await session.get(Product, target_id)
        if p is None:
            raise NotFound("We couldn't find that product.", code="product_not_found")
        before = {"status": p.status}
        if action in ("hide", "remove"):
            # "removed" can only be undone by an admin (Studio restore ignores it).
            p.status = "removed"
            seller = await session.get(SellerProfile, p.seller_id)
            if seller is not None:
                session.add(
                    Notification(
                        user_id=seller.user_id,
                        type="moderation.product",
                        payload={
                            "title": f"“{p.title}” was taken down",
                            "body": note
                            or "It was reported and didn't meet our marketplace rules.",
                            "action_url": "/seller/products",
                        },
                    )
                )
        elif action == "restore":
            p.status = "active" if p.published_at else "draft"
    else:
        raise ValidationFailed("Unknown content type.", code="invalid_target")

    open_flags = (
        await session.scalars(
            select(ContentFlag).where(
                ContentFlag.target_type == target_type,
                ContentFlag.target_id == target_id,
                ContentFlag.status == "open",
            )
        )
    ).all()
    resolution = {
        "dismiss": "dismissed",
        "hide": "taken_down",
        "remove": "taken_down",
        "restore": "restored",
    }[action]
    for f in open_flags:
        f.status, f.resolution, f.resolved_by, f.resolved_at = "resolved", resolution, admin.id, now
    audit_service.record(
        session,
        actor_id=admin.id,
        action=f"moderation.{target_type}.{action}",
        target_type=target_type,
        target_id=target_id,
        before=before,
        after={"resolution": resolution, "reports": len(open_flags)},
        reason=note,
        ip=ip,
    )
    await session.commit()
