"""Order history seed: Marco (collector@queneth.test) has an order in every
status (spec §13). Each one goes through the real checkout and the real state
machine, so escrow, refunds, releases, stock and points are all ledgered and
`reconcile()` still reports zero drift. Idempotent: skipped once Marco has orders.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import utcnow
from app.models import User
from app.models.catalog import CartItem, Product, Review, SellerProfile, Variant
from app.models.commerce import Address, Order, OrderItem
from app.schemas.commerce import CheckoutRequest
from app.services import fulfilment_service as fs
from app.services import order_service, review_service
from app.services.geo_service import GeoService

BUYER_EMAIL = "collector@queneth.test"
DEMO_PIN = "123456"

# (boutique, final status). Paths below drive each one there.
PLAN = [
    ("nocturne-parfums", "PAID"),
    ("casa-ilaya", "PROCESSING"),
    ("obra-leather", "SHIPPED"),
    ("kintsu-jewels", "DELIVERED"),
    ("nocturne-parfums", "COMPLETED"),
    ("rue-solenne", "CANCELLED"),
    ("sable-and-thread", "RETURN_REQUESTED"),
    ("maison-verde", "REFUNDED"),
]

SHIP = [("seller", "PROCESSING", None), ("seller", "SHIPPED", None), ("seller", "DELIVERED", None)]
RETURN = ("buyer", "RETURN_REQUESTED", "The strap colour doesn't match the product photos.")
PATHS: dict[str, list[tuple[str, str, str | None]]] = {
    "PAID": [],
    "PROCESSING": SHIP[:1],
    "SHIPPED": SHIP[:2],
    "DELIVERED": SHIP,
    "COMPLETED": [*SHIP, ("buyer", "COMPLETED", None)],
    "CANCELLED": [("buyer", "CANCELLED", "Found it in another colour elsewhere.")],
    "RETURN_REQUESTED": [*SHIP, RETURN],
    "REFUNDED": [*SHIP, RETURN, ("seller", "REFUNDED", "Sorry about that. Refund approved.")],
}


async def _address(session: AsyncSession, buyer: User) -> Address:
    existing = await session.scalar(select(Address).where(Address.user_id == buyer.id))
    if existing:
        return existing
    names = GeoService(session, get_settings()).resolve_barangay("137404001")
    address = Address(
        user_id=buyer.id,
        label="Home",
        recipient=buyer.name,
        phone="+639175550199",
        line1="22 Scout Rallos St.",
        barangay_code="137404001",
        barangay=names["barangay"] or "",
        city=names["city"] or "",
        province=names["province"],
        region=names["region"] or "",
        zip="1103",
        is_default=True,
    )
    session.add(address)
    await session.commit()
    return address


async def _variant(session: AsyncSession, boutique: str, taken: set[uuid.UUID]) -> Variant | None:
    rows = await session.scalars(
        select(Variant)
        .join(Product, Product.id == Variant.product_id)
        .join(SellerProfile, SellerProfile.id == Product.seller_id)
        .where(
            SellerProfile.slug == boutique,
            Product.status == "active",
            Product.deleted_at.is_(None),
            Product.published_at <= utcnow(),
            Variant.stock >= 3,
        )
        .order_by(Variant.price_qc)
        .limit(10)
    )
    for v in rows.all():
        if v.id not in taken:
            return v
    return None


async def seed_orders(session: AsyncSession) -> int:
    settings = get_settings()
    buyer = await session.scalar(select(User).where(User.email == BUYER_EMAIL))
    if buyer is None:
        return 0
    if await session.scalar(select(Order.id).where(Order.buyer_id == buyer.id).limit(1)):
        return 0
    address = await _address(session, buyer)
    taken: set[uuid.UUID] = set()
    made = 0
    for n, (boutique, final) in enumerate(PLAN, start=1):
        variant = await _variant(session, boutique, taken)
        if variant is None:
            continue
        taken.add(variant.id)
        session.add(CartItem(user_id=buyer.id, variant_id=variant.id, qty=1))
        await session.commit()
        order, _ = await order_service.checkout(
            session,
            settings,
            buyer,
            CheckoutRequest(
                address_id=address.id, pin=DEMO_PIN, expected_total_qc=variant.price_qc
            ),
            f"seed-order-{n}",
        )
        sub = order.sub_orders[0]
        seller = await session.get(SellerProfile, sub.seller_id)
        seller_user = await session.get(User, seller.user_id) if seller else None
        for who, to, text in PATHS[final]:
            actor = buyer if who == "buyer" else seller_user
            await fs.transition(
                session,
                settings,
                actor,
                sub.id,
                to,
                note=text,
                reason=text,
                tracking_no=f"QNX-{order.number[-4:]}-{n:02}" if to == "SHIPPED" else None,
            )
        if final == "COMPLETED":
            item = await session.scalar(select(OrderItem).where(OrderItem.sub_order_id == sub.id))
            if item is not None:
                session.add(
                    Review(
                        product_id=item.product_id,
                        buyer_id=buyer.id,
                        order_item_id=item.id,
                        rating=5,
                        title="Lasts all evening",
                        body="Opens bright, settles into something warm and close to the skin. "
                        "Arrived beautifully wrapped.",
                        photos=[],
                        variant_label=" · ".join(item.options_snapshot.values()) or None,
                    )
                )
                await session.flush()
                await review_service.refresh_rating(session, item.product_id)
                await session.commit()
        made += 1
    return made
