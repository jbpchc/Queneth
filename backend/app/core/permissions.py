"""Role → permission map and the single `can()` check (spec §7).

Every capability in the RBAC matrix is a `Permission`. Each role grants a
permission with a *scope*:

- ``ANY``: on every resource (admin moderation, platform tools)
- ``OWN``: only on resources the user owns (a seller's own products, a buyer's
  own orders). Ownership is checked here, in the same helper, when a resource
  is passed; list queries must also be owner-scoped in the service (no IDOR).

Routers gate with `require_permission(...)`; services call `assert_can(...)`
before every mutation. Hiding a button in the UI is never access control.
"""

from enum import StrEnum
from typing import Any, Protocol

from app.core.errors import PermissionDenied


class Role(StrEnum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    ADMIN = "ADMIN"


class Permission(StrEnum):
    # Shopping
    WISHLIST_MANAGE = "wishlist:manage"
    CART_MANAGE = "cart:manage"
    BOUTIQUE_FOLLOW = "boutique:follow"
    ORDER_CHECKOUT = "order:checkout"
    ORDER_VIEW = "order:view"
    REVIEW_WRITE = "review:write"
    SELLER_APPLY = "seller:apply"
    PROFILE_MANAGE = "profile:manage"
    # Wallet
    WALLET_VIEW = "wallet:view"
    WALLET_TOPUP = "wallet:topup"
    WALLET_VIEW_PLATFORM = "wallet:view_platform"
    WALLET_GRANT = "wallet:grant"
    WALLET_REVERSE = "wallet:reverse"
    # Selling
    PRODUCT_CREATE = "product:create"
    PRODUCT_UPDATE = "product:update"
    PRODUCT_ARCHIVE = "product:archive"
    INVENTORY_MANAGE = "inventory:manage"
    INVENTORY_VIEW = "inventory:view"
    ORDER_FULFILL = "order:fulfill"
    ORDER_OVERRIDE = "order:override"
    REVIEW_REPLY = "review:reply"
    DROP_MANAGE = "drop:manage"
    VOUCHER_MANAGE = "voucher:manage"
    EARNINGS_VIEW = "earnings:view"
    MEDIA_UPLOAD = "media:upload"
    # Platform
    REVIEW_MODERATE = "review:moderate"
    SELLER_APPROVE = "seller:approve"
    USER_BAN = "user:ban"
    USER_MANAGE_ROLES = "user:manage_roles"
    USER_VIEW = "user:view"
    CATALOG_MANAGE = "catalog:manage"
    ANALYTICS_VIEW = "analytics:view"
    AUDIT_VIEW = "audit:view"
    INTEGRATIONS_VIEW = "integrations:view"
    INTEGRATIONS_MANAGE = "integrations:manage"


class Scope(StrEnum):
    OWN = "own"
    ANY = "any"


P = Permission
OWN, ANY = Scope.OWN, Scope.ANY

# Buyers act on their own wishlist, bag, orders, reviews and wallet.
_BUYER: dict[Permission, Scope] = {
    P.WISHLIST_MANAGE: OWN,
    P.CART_MANAGE: OWN,
    P.BOUTIQUE_FOLLOW: OWN,
    P.ORDER_CHECKOUT: OWN,
    P.ORDER_VIEW: OWN,
    P.REVIEW_WRITE: OWN,  # verified purchasers only; enforced in review_service
    P.PROFILE_MANAGE: OWN,
    P.WALLET_VIEW: OWN,
    P.WALLET_TOPUP: OWN,
}

# Sellers run a boutique and nothing else: they don't shop (no wishlist, bag,
# checkout or top-ups). A seller account applies once; Studio tools work once
# an admin approves the boutique (ownership comes from an approved profile).
# Their QueWallet holds sales released from escrow, for viewing and withdrawal.
_SELLER: dict[Permission, Scope] = {
    P.SELLER_APPLY: OWN,
    P.PROFILE_MANAGE: OWN,
    P.WALLET_VIEW: OWN,
    P.PRODUCT_CREATE: OWN,
    P.PRODUCT_UPDATE: OWN,
    P.PRODUCT_ARCHIVE: OWN,
    P.INVENTORY_MANAGE: OWN,
    P.ORDER_FULFILL: OWN,
    P.REVIEW_REPLY: OWN,
    P.DROP_MANAGE: OWN,
    P.VOUCHER_MANAGE: OWN,
    P.EARNINGS_VIEW: OWN,
    P.MEDIA_UPLOAD: OWN,
}

# Admins operate the platform; they don't shop (no wishlist, bag or checkout).
_ADMIN: dict[Permission, Scope] = {
    P.PROFILE_MANAGE: OWN,
    P.PRODUCT_UPDATE: ANY,
    P.PRODUCT_ARCHIVE: ANY,
    P.INVENTORY_VIEW: ANY,
    P.ORDER_VIEW: ANY,
    P.ORDER_OVERRIDE: ANY,
    P.REVIEW_REPLY: ANY,
    P.REVIEW_MODERATE: ANY,
    P.DROP_MANAGE: ANY,
    P.VOUCHER_MANAGE: ANY,
    P.MEDIA_UPLOAD: ANY,
    P.WALLET_VIEW_PLATFORM: ANY,
    P.WALLET_GRANT: ANY,
    P.WALLET_REVERSE: ANY,
    P.SELLER_APPROVE: ANY,
    P.USER_BAN: ANY,
    P.USER_MANAGE_ROLES: ANY,
    P.USER_VIEW: ANY,
    P.CATALOG_MANAGE: ANY,
    P.ANALYTICS_VIEW: ANY,
    P.AUDIT_VIEW: ANY,
    P.INTEGRATIONS_VIEW: ANY,
    P.INTEGRATIONS_MANAGE: ANY,
}

#: Seller Studio tools work only for an approved boutique. A seller account whose
#: application is pending, rejected or suspended keeps just the rest of _SELLER
#: (apply, profile, uploads for the application, and its wallet).
NEEDS_APPROVED_BOUTIQUE: frozenset[Permission] = frozenset({
    P.PRODUCT_CREATE,
    P.PRODUCT_UPDATE,
    P.PRODUCT_ARCHIVE,
    P.INVENTORY_MANAGE,
    P.ORDER_FULFILL,
    P.REVIEW_REPLY,
    P.DROP_MANAGE,
    P.VOUCHER_MANAGE,
    P.EARNINGS_VIEW,
})  # fmt: skip

ROLE_PERMISSIONS: dict[Role, dict[Permission, Scope]] = {
    Role.BUYER: _BUYER,
    Role.SELLER: _SELLER,
    Role.ADMIN: _ADMIN,
}

#: Every account has exactly one role: buyer, seller or admin (chosen at sign-up;
#: admins are seeded). Kept as a hook for roles that remove a permission.
ROLE_EXCLUSIONS: dict[Role, frozenset[Permission]] = {}


def _excluded(roles: list[Role]) -> frozenset[Permission]:
    return frozenset().union(*(ROLE_EXCLUSIONS.get(r, frozenset()) for r in roles))


class Principal(Protocol):
    id: Any
    roles: list[str]
    status: str

    @property
    def seller_id(self) -> Any: ...


def _role_applies(user: Principal, role: Role, permission: Permission) -> bool:
    """The SELLER role grants Studio tools only once the boutique is approved."""
    return not (
        role is Role.SELLER
        and permission in NEEDS_APPROVED_BOUTIQUE
        and getattr(user, "seller_id", None) is None
    )


def _roles_of(user: Principal) -> list[Role]:
    return [Role(r) for r in (user.roles or []) if r in Role.__members__]


def scope_for(user: Principal | None, permission: Permission) -> Scope | None:
    """Widest scope any of the user's roles grants for `permission` (ANY beats OWN)."""
    if user is None or user.status != "active":
        return None
    roles = _roles_of(user)
    if permission in _excluded(roles):
        return None
    scopes = {
        ROLE_PERMISSIONS[role][permission]
        for role in roles
        if permission in ROLE_PERMISSIONS[role] and _role_applies(user, role, permission)
    }
    if Scope.ANY in scopes:
        return Scope.ANY
    return Scope.OWN if scopes else None


def permissions_for(user: Principal | None) -> set[Permission]:
    if user is None or user.status != "active":
        return set()
    roles = _roles_of(user)
    granted = {
        perm for role in roles for perm in ROLE_PERMISSIONS[role] if _role_applies(user, role, perm)
    }
    return granted - _excluded(roles)


def is_owner(user: Principal, resource: Any) -> bool:
    """Ownership rules, in one place:

    - seller-owned resources (products, drops, sub-orders) carry `seller_id`
    - user-owned resources (orders, addresses, wallets) carry `buyer_id` or `user_id`
    """
    if (seller_id := getattr(resource, "seller_id", None)) is not None:
        return user.seller_id is not None and seller_id == user.seller_id
    for attr in ("buyer_id", "user_id", "owner_id"):
        if (owner := getattr(resource, attr, None)) is not None:
            return owner == user.id
    return False


def can(user: Principal | None, permission: Permission, resource: Any = None) -> bool:
    scope = scope_for(user, permission)
    if scope is None:
        return False
    if resource is None or scope is Scope.ANY:
        return True
    assert user is not None
    return is_owner(user, resource)


def assert_can(user: Principal | None, permission: Permission, resource: Any = None) -> None:
    if not can(user, permission, resource):
        raise PermissionDenied(details={"permission": str(permission)})
