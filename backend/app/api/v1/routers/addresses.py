"""Address book (PSGC-validated). Owner-scoped: another user's address is a 404."""

import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import AppSettings, DbSession, require_permission
from app.core.permissions import Permission
from app.models.commerce import Address
from app.models.user import User
from app.schemas.commerce import AddressIn, AddressOut
from app.services import address_service

router = APIRouter(prefix="/addresses", tags=["addresses"])

# Delivery addresses are for shopping: buyer accounts only.
Owner = Depends(require_permission(Permission.ORDER_CHECKOUT))


def out(a: Address) -> AddressOut:
    return AddressOut.model_validate(a, from_attributes=True)


@router.get("", response_model=list[AddressOut], summary="Your saved addresses (default first)")
async def list_addresses(session: DbSession, user: User = Owner) -> list[AddressOut]:
    return [out(a) for a in await address_service.list_for(session, user)]


@router.post(
    "", response_model=AddressOut, status_code=status.HTTP_201_CREATED, summary="Add an address"
)
async def create_address(
    body: AddressIn, session: DbSession, settings: AppSettings, user: User = Owner
) -> AddressOut:
    return out(await address_service.create(session, user, body, settings))


@router.put("/{address_id}", response_model=AddressOut, summary="Edit an address")
async def update_address(
    address_id: uuid.UUID,
    body: AddressIn,
    session: DbSession,
    settings: AppSettings,
    user: User = Owner,
) -> AddressOut:
    return out(await address_service.update_address(session, user, address_id, body, settings))


@router.post("/{address_id}/default", response_model=AddressOut, summary="Make default")
async def make_default(address_id: uuid.UUID, session: DbSession, user: User = Owner) -> AddressOut:
    return out(await address_service.set_default(session, user, address_id))


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an address")
async def delete_address(address_id: uuid.UUID, session: DbSession, user: User = Owner) -> None:
    await address_service.delete(session, user, address_id)
