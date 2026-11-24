"""Shopper actions: wishlist, bag, follow boutiques, drop "Notify me".

Every query is owner-scoped (user_id == current user), and every mutation
checks its permission first (enforcement layer 2).
"""

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Permission, assert_can
from app.core.security import utcnow
from app.models.catalog import (
    CartItem,
    Drop,
    DropSubscription,
    Follow,
    Product,
    SellerProfile,
    Variant,
    WishlistItem,
)
from app.models.user import User
from app.schemas.shop import BagGroup, BagItem, BagOut, WishlistEntry, WishlistOut
from app.services import board_service, voucher_service
from app.services.catalog_service import CatalogService

MAX_QTY = 10


async def _visible_product(session: AsyncSession, product_id: uuid.UUID) -> Product:
    p = await session.get(Product, product_id)
    if (
        p is None
        or p.status != "active"
        or p.deleted_at is not None
        or not p.published_at
        or p.published_at > utcnow()
    ):
        raise NotFound("This piece isn't available.", code="product_not_found")
    return p


# ─── Wishlist ──────────────────────────────────────────────────────────────


async def wishlist_ids(session: AsyncSession, user: User) -> list[uuid.UUID]:
    assert_can(user, Permission.WISHLIST_MANAGE)
    return list(
        (
            await session.scalars(
                select(WishlistItem.product_id).where(WishlistItem.user_id == user.id)
            )
        ).all()
    )


async def save(session: AsyncSession, user: User, product_id: uuid.UUID) -> int:
    """Idempotent. Returns the product's new save count."""
    assert_can(user, Permission.WISHLIST_MANAGE)
    product = await _visible_product(session, product_id)
    exists = await session.scalar(
        select(WishlistItem.id).where(
            WishlistItem.user_id == user.id, WishlistItem.product_id == product_id
        )
    )
    if not exists:
        session.add(
            WishlistItem(
                user_id=user.id, product_id=product_id, saved_price_qc=product.min_price_qc
            )
        )
        await session.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(wishlist_count=Product.wishlist_count + 1)
        )
        await session.commit()
    return await session.scalar(select(Product.wishlist_count).where(Product.id == product_id)) or 0


async def unsave(session: AsyncSession, user: User, product_id: uuid.UUID) -> None:
    assert_can(user, Permission.WISHLIST_MANAGE)
    result = await session.execute(
        delete(WishlistItem).where(
            WishlistItem.user_id == user.id, WishlistItem.product_id == product_id
        )
    )
    if result.rowcount:
        await session.execute(
            update(Product)
            .where(Product.id == product_id, Product.wishlist_count > 0)
            .values(wishlist_count=Product.wishlist_count - 1)
        )
    await session.commit()


async def wishlist(session: AsyncSession, catalog: CatalogService, user: User) -> WishlistOut:
    assert_can(user, Permission.WISHLIST_MANAGE)
    rows = (
        await session.execute(
            select(WishlistItem, Product)
            .join(Product, Product.id == WishlistItem.product_id)
            .where(WishlistItem.user_id == user.id, Product.deleted_at.is_(None))
            .order_by(WishlistItem.created_at.desc())
        )
    ).all()
    live = await catalog.live_drop_product_ids()
    entries = [
        WishlistEntry(
            product=catalog.card(p, live),
            saved_at=item.created_at,
            saved_price_qc=item.saved_price_qc,
            # Indicators are only shown when true (no fake urgency).
            price_dropped=bool(item.saved_price_qc and p.min_price_qc < item.saved_price_qc),
            available=p.status == "active" and p.total_stock > 0,
            board_id=item.board_id,
        )
        for item, p in rows
    ]
    boards = await board_service.list_for(session, user)
    return WishlistOut(items=entries, count=len(entries), boards=boards)


# ─── Bag ───────────────────────────────────────────────────────────────────


async def bag(
    session: AsyncSession,
    catalog: CatalogService,
    user: User,
    only: list[uuid.UUID] | None = None,
) -> BagOut:
    """The bag, or with `only` just those lines (the "Buy now" checkout)."""
    assert_can(user, Permission.CART_MANAGE)
    rows = (
        await session.execute(
            select(CartItem, Variant, Product)
            .join(Variant, Variant.id == CartItem.variant_id)
            .join(Product, Product.id == Variant.product_id)
            .where(CartItem.user_id == user.id)
            .where(CartItem.id.in_(only) if only else True)
            .order_by(CartItem.created_at)
        )
    ).all()
    live = await catalog.live_drop_product_ids()
    vouchers = await voucher_service.applied(session, user.id)
    redeemed = await voucher_service.redeemed_ids(session, user.id) if vouchers else set()
    groups: dict[uuid.UUID, BagGroup] = {}
    saved: list[BagItem] = []
    count = 0
    for item, variant, product in rows:
        available = product.status == "active" and product.deleted_at is None and variant.stock > 0
        line = BagItem(
            id=item.id,
            qty=item.qty,
            variant_id=variant.id,
            options=variant.options,
            unit_price_qc=variant.price_qc,
            compare_at_qc=variant.compare_at_qc,
            line_total_qc=variant.price_qc * item.qty,
            stock=variant.stock,
            available=available,
            product=catalog.card(product, live, color=variant.options.get("color")),
        )
        if item.saved_for_later:
            saved.append(line)
            continue
        group = groups.setdefault(
            product.seller_id,
            BagGroup(
                boutique=catalog.boutique_card(product.seller),
                items=[],
                subtotal_qc=0,
                voucher=None,
                discount_qc=0,
                total_qc=0,
            ),
        )
        group.items.append(line)
        if available:
            group.subtotal_qc += line.line_total_qc
            count += item.qty
    # UX: Goal-Gradient — a voucher below its minimum spend says how much more to add.
    for seller_id, group in groups.items():
        voucher = vouchers.get(seller_id)
        if voucher is not None:
            group.voucher = voucher_service.evaluate(
                voucher, group.subtotal_qc, redeemed=voucher.id in redeemed
            )
            group.discount_qc = group.voucher.discount_qc
        group.total_qc = group.subtotal_qc - group.discount_qc
    out = list(groups.values())
    return BagOut(
        groups=out,
        saved=saved,
        item_count=count,
        subtotal_qc=sum(g.subtotal_qc for g in out),
        discount_qc=sum(g.discount_qc for g in out),
        total_qc=sum(g.total_qc for g in out),
    )


async def add_to_bag(
    session: AsyncSession, user: User, variant_id: uuid.UUID, qty: int, *, buy_now: bool = False
) -> CartItem:
    """Adds `qty` to the line (or, for "Buy now", sets it to `qty`); returns the line."""
    assert_can(user, Permission.CART_MANAGE)
    variant = await session.get(Variant, variant_id)
    if variant is None:
        raise NotFound("That size or color isn't available.", code="variant_not_found")
    product = await _visible_product(session, variant.product_id)
    if user.seller_id is not None and product.seller_id == user.seller_id:
        raise Conflict("You can't buy from your own boutique.", code="own_product")
    item = await session.scalar(
        select(CartItem).where(CartItem.user_id == user.id, CartItem.variant_id == variant_id)
    )
    wanted = qty if buy_now else qty + (item.qty if item else 0)
    if variant.stock <= 0:
        raise Conflict("This size just sold out.", code="sold_out")
    if wanted > variant.stock:
        raise Conflict(
            f"Only {variant.stock} left in this option.",
            code="insufficient_stock",
            details={"available": variant.stock},
        )
    if wanted > MAX_QTY:
        raise ValidationFailed(f"You can add up to {MAX_QTY} of one piece.", code="qty_limit")
    if item:
        item.qty = wanted
        item.saved_for_later = False  # adding again brings it back into the bag
    else:
        item = CartItem(user_id=user.id, variant_id=variant_id, qty=qty)
        session.add(item)
    # Seller funnel: views → wishlists → bag adds → orders.
    await session.execute(
        update(Product)
        .where(Product.id == product.id)
        .values(bag_add_count=Product.bag_add_count + 1)
    )
    await session.commit()
    return item


async def set_qty(session: AsyncSession, user: User, item_id: uuid.UUID, qty: int) -> None:
    assert_can(user, Permission.CART_MANAGE)
    item = await session.scalar(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id)
    )
    if item is None:
        raise NotFound("That item isn't in your bag.", code="bag_item_not_found")
    variant = await session.get(Variant, item.variant_id)
    if variant is None or qty > variant.stock:
        raise Conflict(
            f"Only {variant.stock if variant else 0} left in this option.",
            code="insufficient_stock",
            details={"available": variant.stock if variant else 0},
        )
    item.qty = qty
    await session.commit()


async def remove_from_bag(session: AsyncSession, user: User, item_id: uuid.UUID) -> None:
    assert_can(user, Permission.CART_MANAGE)
    await session.execute(
        delete(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id)
    )
    await session.commit()


async def set_saved_for_later(
    session: AsyncSession, user: User, item_id: uuid.UUID, saved: bool
) -> None:
    """UX: Zeigarnik — "Save for later" keeps a piece one tap away without
    counting it in today's total."""
    assert_can(user, Permission.CART_MANAGE)
    item = await session.scalar(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user.id)
    )
    if item is None:
        raise NotFound("That item isn't in your bag.", code="bag_item_not_found")
    item.saved_for_later = saved
    await session.commit()


async def bag_count(session: AsyncSession, user: User) -> int:
    return (
        await session.scalar(
            select(func.coalesce(func.sum(CartItem.qty), 0)).where(
                CartItem.user_id == user.id, CartItem.saved_for_later.is_(False)
            )
        )
        or 0
    )


# ─── Follow & drop notifications ───────────────────────────────────────────


async def _boutique(session: AsyncSession, slug: str) -> SellerProfile:
    s = await session.scalar(
        select(SellerProfile).where(SellerProfile.slug == slug, SellerProfile.status == "approved")
    )
    if s is None:
        raise NotFound("We couldn't find that boutique.", code="boutique_not_found")
    return s


async def follow(session: AsyncSession, user: User, slug: str, on: bool) -> tuple[bool, int]:
    assert_can(user, Permission.BOUTIQUE_FOLLOW)
    seller = await _boutique(session, slug)
    if seller.user_id == user.id:
        raise Conflict("That's your own boutique.", code="own_boutique")
    existing = await session.scalar(
        select(Follow).where(Follow.buyer_id == user.id, Follow.seller_id == seller.id)
    )
    if on and existing is None:
        session.add(Follow(buyer_id=user.id, seller_id=seller.id))
        seller.follower_count += 1
    elif not on and existing is not None:
        await session.delete(existing)
        seller.follower_count = max(0, seller.follower_count - 1)
    await session.commit()
    return on, seller.follower_count


async def notify_drop(session: AsyncSession, user: User, slug: str, on: bool) -> bool:
    assert_can(user, Permission.WISHLIST_MANAGE)
    drop = await session.scalar(select(Drop).where(Drop.slug == slug))
    if drop is None:
        raise NotFound("We couldn't find that drop.", code="drop_not_found")
    if on and drop.starts_at <= utcnow():
        raise Conflict("This drop is already live.", code="drop_live")
    existing = await session.scalar(
        select(DropSubscription).where(
            DropSubscription.user_id == user.id, DropSubscription.drop_id == drop.id
        )
    )
    if on and existing is None:
        session.add(DropSubscription(user_id=user.id, drop_id=drop.id))
    elif not on and existing is not None:
        await session.delete(existing)
    await session.commit()
    return on
