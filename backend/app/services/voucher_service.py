"""Seller vouchers on the bag. One voucher per boutique; the boutique funds the
discount (it comes off that sub-order's escrow payment, spec §11).

`evaluate()` is the single pricing rule, used by the bag view and by checkout,
so the total the buyer reviews is exactly the total they are charged.
"""

import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.core.permissions import Permission, assert_can
from app.core.security import as_aware, utcnow
from app.models.catalog import CartItem, Product, Variant
from app.models.commerce import CartVoucher, Voucher, VoucherRedemption
from app.models.user import User
from app.schemas.commerce import AppliedVoucher


def normalize(code: str) -> str:
    """UX: Postel's Law — ' nocturne15 ' finds NOCTURNE15."""
    return "".join(code.split()).upper()


def discount_for(voucher: Voucher, items_total_qc: int) -> int:
    if voucher.type == "percent":
        return items_total_qc * voucher.value // 100  # floor: never over-discount
    return min(voucher.value, items_total_qc)


def problem_for(
    voucher: Voucher, items_total_qc: int, *, redeemed: bool, now: datetime | None = None
) -> str | None:
    """Why the voucher can't apply right now, or None."""
    now = now or utcnow()
    if not voucher.is_active:
        return "This voucher is no longer active."
    if voucher.starts_at and as_aware(voucher.starts_at) > now:
        return "This voucher isn't active yet."
    if voucher.ends_at and as_aware(voucher.ends_at) <= now:
        return "This voucher has expired."
    if voucher.used_count >= voucher.max_uses:
        return "This voucher has been fully claimed."
    if redeemed:
        return "You've already used this voucher."
    if items_total_qc < voucher.min_spend_qc:
        short = voucher.min_spend_qc - items_total_qc
        return f"Add {short:,} QC more from this boutique to use it."
    return None


def evaluate(
    voucher: Voucher, items_total_qc: int, *, redeemed: bool, now: datetime | None = None
) -> AppliedVoucher:
    problem = problem_for(voucher, items_total_qc, redeemed=redeemed, now=now)
    return AppliedVoucher(
        id=voucher.id,
        code=voucher.code,
        description=voucher.description,
        discount_qc=0 if problem else discount_for(voucher, items_total_qc),
        problem=problem,
    )


async def redeemed_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await session.scalars(
        select(VoucherRedemption.voucher_id).where(VoucherRedemption.user_id == user_id)
    )
    return set(rows.all())


async def applied(session: AsyncSession, user_id: uuid.UUID) -> dict[uuid.UUID, Voucher]:
    """The bag's vouchers, keyed by boutique (seller profile id)."""
    rows = await session.scalars(
        select(CartVoucher).where(CartVoucher.user_id == user_id).order_by(CartVoucher.created_at)
    )
    out: dict[uuid.UUID, Voucher] = {}
    for cv in rows.unique().all():
        if cv.voucher.seller_id is not None:
            out[cv.voucher.seller_id] = cv.voucher  # newest wins if ever duplicated
    return out


async def _bag_total_for(session: AsyncSession, user: User, seller_id: uuid.UUID) -> int:
    rows = (
        await session.execute(
            select(CartItem.qty, Variant.price_qc, Variant.stock, Product.status)
            .join(Variant, Variant.id == CartItem.variant_id)
            .join(Product, Product.id == Variant.product_id)
            .where(
                CartItem.user_id == user.id,
                CartItem.saved_for_later.is_(False),
                Product.seller_id == seller_id,
                Product.deleted_at.is_(None),
            )
        )
    ).all()
    return sum(q * price for q, price, stock, status in rows if status == "active" and stock > 0)


async def apply(session: AsyncSession, user: User, code: str) -> Voucher:
    assert_can(user, Permission.CART_MANAGE)
    voucher = await session.scalar(select(Voucher).where(Voucher.code == normalize(code)))
    if voucher is None or voucher.seller_id is None:
        raise NotFound("We couldn't find that voucher code.", code="voucher_not_found")
    items_total = await _bag_total_for(session, user, voucher.seller_id)
    if items_total == 0:
        raise Conflict(
            "This voucher is for a boutique that isn't in your bag.", code="voucher_not_applicable"
        )
    redeemed = voucher.id in await redeemed_ids(session, user.id)
    # Min spend is the one problem we let through: the bag shows how much more to add.
    problem = problem_for(voucher, max(items_total, voucher.min_spend_qc), redeemed=redeemed)
    if problem:
        raise Conflict(problem, code="voucher_invalid")
    # One voucher per boutique: applying a new one replaces the old.
    current = await applied(session, user.id)
    old = current.get(voucher.seller_id)
    if old is not None and old.id != voucher.id:
        await session.execute(
            delete(CartVoucher).where(
                CartVoucher.user_id == user.id, CartVoucher.voucher_id == old.id
            )
        )
    if old is None or old.id != voucher.id:
        session.add(CartVoucher(user_id=user.id, voucher_id=voucher.id))
    await session.commit()
    return voucher


async def remove(session: AsyncSession, user: User, voucher_id: uuid.UUID) -> None:
    assert_can(user, Permission.CART_MANAGE)
    await session.execute(
        delete(CartVoucher).where(
            CartVoucher.user_id == user.id, CartVoucher.voucher_id == voucher_id
        )
    )
    await session.commit()
