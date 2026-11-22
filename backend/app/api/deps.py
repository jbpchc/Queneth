"""Request-scoped dependencies: DB session, current user, role and permission gates.

This is enforcement layer 1 (spec §7): every protected route declares its
requirement here. A missing or invalid token → 401; a wrong role → 403.
"""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import NotAuthenticated, PermissionDenied
from app.core.permissions import Permission, Role, can
from app.core.security import ACCESS_COOKIE, decode_token
from app.db.session import get_session
from app.models.user import User

DbSession = Annotated[AsyncSession, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_session_factory(request: Request) -> Callable[[], AsyncSession]:
    """Session factory for work that outlives the request (background email
    delivery). Lives on app.state so tests can point it at the test database."""
    return request.app.state.session_factory


SessionFactoryDep = Annotated[Callable[[], AsyncSession], Depends(get_session_factory)]


async def get_optional_user(
    request: Request, session: DbSession, settings: AppSettings
) -> User | None:
    """The signed-in user, or None for guests. Always reloaded from the database
    so role changes and bans apply immediately, not after the token expires."""
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    payload = decode_token(token, "access", settings)
    return await session.get(User, payload.sub)


async def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise NotAuthenticated()
    if user.is_banned:
        raise PermissionDenied("This account has been suspended.", code="account_banned")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_role(*roles: Role | str) -> Callable[..., Coroutine[Any, Any, User]]:
    """`Depends(require_role("SELLER"))` — passes if the user holds any listed role."""
    wanted = {str(r) for r in roles}

    async def dependency(user: CurrentUser) -> User:
        if not wanted.intersection(user.roles or []):
            raise PermissionDenied(details={"required_roles": sorted(wanted)})
        return user

    return dependency


def require_permission(permission: Permission) -> Callable[..., Coroutine[Any, Any, User]]:
    """`Depends(require_permission(Permission.PRODUCT_UPDATE))` — role-level gate.
    Ownership of a specific resource is re-checked in the service via assert_can."""

    async def dependency(user: CurrentUser) -> User:
        if not can(user, permission):
            raise PermissionDenied(details={"permission": str(permission)})
        return user

    return dependency


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
