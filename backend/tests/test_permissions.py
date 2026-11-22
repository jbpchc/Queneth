"""The RBAC matrix from spec §7, checked against `can()` directly."""

import uuid
from dataclasses import dataclass, field

import pytest

from app.core.errors import PermissionDenied
from app.core.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
    Scope,
    assert_can,
    can,
    permissions_for,
)

P = Permission


@dataclass
class FakeUser:
    roles: list[str]
    status: str = "active"
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    seller_id: uuid.UUID | None = None


@dataclass
class FakeProduct:
    seller_id: uuid.UUID


@dataclass
class FakeOrder:
    buyer_id: uuid.UUID


def buyer() -> FakeUser:
    return FakeUser(roles=["BUYER"])


def seller() -> FakeUser:
    return FakeUser(roles=["BUYER", "SELLER"], seller_id=uuid.uuid4())


def admin() -> FakeUser:
    return FakeUser(roles=["ADMIN"])


# (permission, guest, buyer, seller, admin) — straight from the spec's table.
MATRIX = [
    (P.WISHLIST_MANAGE, False, True, True, False),
    (P.CART_MANAGE, False, True, True, False),
    (P.BOUTIQUE_FOLLOW, False, True, True, False),
    (P.ORDER_CHECKOUT, False, True, True, False),
    (P.REVIEW_WRITE, False, True, True, False),
    (P.REVIEW_MODERATE, False, False, False, True),
    (P.SELLER_APPLY, False, True, False, False),
    (P.PRODUCT_CREATE, False, False, True, False),
    (P.PRODUCT_UPDATE, False, False, True, True),
    (P.PRODUCT_ARCHIVE, False, False, True, True),
    (P.INVENTORY_MANAGE, False, False, True, False),
    (P.INVENTORY_VIEW, False, False, False, True),
    (P.ORDER_FULFILL, False, False, True, False),
    (P.ORDER_OVERRIDE, False, False, False, True),
    (P.REVIEW_REPLY, False, False, True, True),
    (P.DROP_MANAGE, False, False, True, True),
    (P.VOUCHER_MANAGE, False, False, True, True),
    (P.WALLET_VIEW, False, True, True, False),
    (P.EARNINGS_VIEW, False, False, True, False),
    (P.WALLET_VIEW_PLATFORM, False, False, False, True),
    (P.WALLET_GRANT, False, False, False, True),
    (P.WALLET_REVERSE, False, False, False, True),
    (P.SELLER_APPROVE, False, False, False, True),
    (P.USER_BAN, False, False, False, True),
    (P.USER_MANAGE_ROLES, False, False, False, True),
    (P.CATALOG_MANAGE, False, False, False, True),
    (P.ANALYTICS_VIEW, False, False, False, True),
    (P.AUDIT_VIEW, False, False, False, True),
    (P.INTEGRATIONS_VIEW, False, False, False, True),
    (P.INTEGRATIONS_MANAGE, False, False, False, True),
]


@pytest.mark.parametrize(("perm", "guest", "as_buyer", "as_seller", "as_admin"), MATRIX)
def test_matrix(perm, guest, as_buyer, as_seller, as_admin):
    assert can(None, perm) is guest
    assert can(buyer(), perm) is as_buyer
    assert can(seller(), perm) is as_seller
    assert can(admin(), perm) is as_admin


def test_every_permission_is_granted_to_someone():
    granted = {p for perms in ROLE_PERMISSIONS.values() for p in perms}
    assert granted == set(Permission)


def test_buyer_cannot_call_seller_actions():
    b = buyer()
    for perm in (P.PRODUCT_CREATE, P.PRODUCT_UPDATE, P.INVENTORY_MANAGE, P.ORDER_FULFILL):
        assert not can(b, perm)
        with pytest.raises(PermissionDenied):
            assert_can(b, perm)


def test_seller_a_cannot_edit_seller_b_product():
    a, b = seller(), seller()
    product_of_b = FakeProduct(seller_id=b.seller_id)  # type: ignore[arg-type]
    assert can(b, P.PRODUCT_UPDATE, product_of_b)
    assert not can(a, P.PRODUCT_UPDATE, product_of_b)
    assert not can(a, P.PRODUCT_ARCHIVE, product_of_b)
    with pytest.raises(PermissionDenied):
        assert_can(a, P.PRODUCT_UPDATE, product_of_b)


def test_seller_without_profile_owns_nothing():
    s = FakeUser(roles=["BUYER", "SELLER"], seller_id=None)
    assert not can(s, P.PRODUCT_UPDATE, FakeProduct(seller_id=uuid.uuid4()))


def test_admin_moderates_any_product():
    assert can(admin(), P.PRODUCT_UPDATE, FakeProduct(seller_id=uuid.uuid4()))


def test_non_admin_cannot_grant_credits():
    for user in (None, buyer(), seller()):
        assert not can(user, P.WALLET_GRANT)
        assert not can(user, P.WALLET_REVERSE)
    assert can(admin(), P.WALLET_GRANT)


def test_buyer_owns_only_their_orders():
    b = buyer()
    assert can(b, P.ORDER_VIEW, FakeOrder(buyer_id=b.id))
    assert not can(b, P.ORDER_VIEW, FakeOrder(buyer_id=uuid.uuid4()))
    assert can(admin(), P.ORDER_VIEW, FakeOrder(buyer_id=uuid.uuid4()))


def test_banned_user_has_no_permissions():
    banned = FakeUser(roles=["BUYER", "SELLER"], status="banned", seller_id=uuid.uuid4())
    assert permissions_for(banned) == set()
    assert not can(banned, P.CART_MANAGE)


def test_unknown_roles_are_ignored():
    assert permissions_for(FakeUser(roles=["SUPERUSER"])) == set()


def test_seller_scope_is_own_and_admin_scope_is_any():
    assert ROLE_PERMISSIONS[Role.SELLER][P.PRODUCT_UPDATE] is Scope.OWN
    assert ROLE_PERMISSIONS[Role.ADMIN][P.PRODUCT_UPDATE] is Scope.ANY
