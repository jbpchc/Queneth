"""Address book. Place names come from the PSGC snapshot via the barangay code,
so every saved address is a real, consistent Region → Barangay chain."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound
from app.core.permissions import Permission, assert_can
from app.models.commerce import Address
from app.models.user import User
from app.schemas.commerce import AddressIn
from app.services.geo_service import GeoService

MAX_ADDRESSES = 10


async def list_for(session: AsyncSession, user: User) -> list[Address]:
    assert_can(user, Permission.PROFILE_MANAGE)
    return list(
        (
            await session.scalars(
                select(Address)
                .where(Address.user_id == user.id)
                .order_by(Address.is_default.desc(), Address.created_at)
            )
        ).all()
    )


async def owned(session: AsyncSession, user: User, address_id: uuid.UUID) -> Address:
    row = await session.get(Address, address_id)
    if row is None or row.user_id != user.id:  # IDOR-safe: someone else's looks missing
        raise NotFound("We couldn't find that address.", code="address_not_found")
    return row


async def _make_default(session: AsyncSession, user: User, address: Address) -> None:
    await session.execute(
        update(Address)
        .where(Address.user_id == user.id, Address.id != address.id)
        .values(is_default=False)
    )
    address.is_default = True


def _apply(address: Address, data: AddressIn, settings: Settings, session: AsyncSession) -> None:
    names = GeoService(session, settings).resolve_barangay(data.barangay_code)
    address.label, address.recipient, address.phone = data.label, data.recipient, data.phone
    address.line1, address.zip, address.barangay_code = data.line1, data.zip, data.barangay_code
    address.barangay = names["barangay"] or ""
    address.city = names["city"] or ""
    address.province = names["province"]
    address.region = names["region"] or ""


async def create(session: AsyncSession, user: User, data: AddressIn, settings: Settings) -> Address:
    assert_can(user, Permission.PROFILE_MANAGE)
    count = await session.scalar(select(func.count()).where(Address.user_id == user.id)) or 0
    if count >= MAX_ADDRESSES:
        raise Conflict(f"You can save up to {MAX_ADDRESSES} addresses.", code="address_limit")
    row = Address(user_id=user.id)
    _apply(row, data, settings, session)
    session.add(row)
    await session.flush()
    if data.is_default or count == 0:  # the first address is the default
        await _make_default(session, user, row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_address(
    session: AsyncSession, user: User, address_id: uuid.UUID, data: AddressIn, settings: Settings
) -> Address:
    row = await owned(session, user, address_id)
    _apply(row, data, settings, session)
    if data.is_default:
        await _make_default(session, user, row)
    await session.commit()
    await session.refresh(row)
    return row


async def set_default(session: AsyncSession, user: User, address_id: uuid.UUID) -> Address:
    row = await owned(session, user, address_id)
    await _make_default(session, user, row)
    await session.commit()
    await session.refresh(row)
    return row


async def delete(session: AsyncSession, user: User, address_id: uuid.UUID) -> None:
    row = await owned(session, user, address_id)
    was_default = row.is_default
    await session.delete(row)
    await session.flush()
    if was_default:
        nxt = await session.scalar(
            select(Address).where(Address.user_id == user.id).order_by(Address.created_at)
        )
        if nxt:
            nxt.is_default = True
    await session.commit()
