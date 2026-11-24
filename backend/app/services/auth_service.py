"""Registration, sign-in and refresh-token rotation."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotAuthenticated, PermissionDenied
from app.core.permissions import Role
from app.core.security import (
    as_aware,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    utcnow,
    verify_password,
)
from app.models.user import RefreshToken, User, UserStatus
from app.schemas.auth import LoginRequest, RegisterRequest

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class IssuedTokens:
    access: str
    refresh: str


@dataclass(frozen=True)
class ClientInfo:
    ip: str | None = None
    user_agent: str | None = None


async def register(
    session: AsyncSession, data: RegisterRequest, settings: Settings, client: ClientInfo
) -> tuple[User, IssuedTokens]:
    """Create a BUYER or SELLER account and sign it in. ADMIN can never be self-registered."""
    existing = await session.scalar(select(User.id).where(User.email == data.email))
    if existing:
        raise Conflict(
            "An account with this email already exists. Try signing in.",
            code="email_taken",
            details=[{"field": "email", "message": "Already registered."}],
        )
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        roles=[Role.SELLER.value if data.account_type == "seller" else Role.BUYER.value],
        status=UserStatus.ACTIVE.value,
        last_login_at=utcnow(),
        seller_profile=None,  # new accounts have no boutique; avoids a lazy load later
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:  # lost a race with an identical sign-up
        await session.rollback()
        raise Conflict("An account with this email already exists.", code="email_taken") from exc
    tokens = await _issue(session, user, settings, client, family_id=None)
    await session.commit()
    log.info("user_registered", user_id=str(user.id))
    return user, tokens


async def login(
    session: AsyncSession, data: LoginRequest, settings: Settings, client: ClientInfo
) -> tuple[User, IssuedTokens]:
    user = await session.scalar(select(User).where(User.email == data.email))
    # verify_password runs a dummy hash for unknown emails (no timing leak), and
    # the message never says which half was wrong (no account enumeration).
    if not verify_password(data.password, user.password_hash if user else None) or user is None:
        raise NotAuthenticated("That email and password don't match.", code="invalid_credentials")
    if user.is_banned:
        raise PermissionDenied("This account has been suspended.", code="account_banned")
    user.last_login_at = utcnow()
    tokens = await _issue(session, user, settings, client, family_id=None)
    await session.commit()
    return user, tokens


async def refresh(
    session: AsyncSession, refresh_jwt: str | None, settings: Settings, client: ClientInfo
) -> tuple[User, IssuedTokens]:
    """Rotate a refresh token. Reusing an already-rotated token revokes the
    whole family, logging out every session that descended from that login."""
    if not refresh_jwt:
        raise NotAuthenticated(code="no_refresh_token")
    payload = decode_token(refresh_jwt, "refresh", settings)
    row = await session.get(RefreshToken, payload.jti, with_for_update=True)
    if row is None or row.user_id != payload.sub:
        raise NotAuthenticated(code="invalid_token")

    now = utcnow()
    if row.revoked_at is not None:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await session.commit()
        log.warning("refresh_token_reuse", user_id=str(row.user_id), family_id=str(row.family_id))
        raise NotAuthenticated("Please sign in again.", code="refresh_reused")
    if as_aware(row.expires_at) <= now:
        raise NotAuthenticated(
            "Your session has expired. Please sign in again.", code="token_expired"
        )

    user = await session.get(User, row.user_id)
    if user is None:
        raise NotAuthenticated(code="invalid_token")
    if user.is_banned:
        raise PermissionDenied("This account has been suspended.", code="account_banned")

    tokens = await _issue(session, user, settings, client, family_id=row.family_id, rotated=row)
    await session.commit()
    return user, tokens


async def logout(session: AsyncSession, refresh_jwt: str | None, settings: Settings) -> None:
    """Revoke the presented refresh token. Always succeeds (idempotent)."""
    if not refresh_jwt:
        return
    try:
        payload = decode_token(refresh_jwt, "refresh", settings)
    except NotAuthenticated:
        return
    row = await session.get(RefreshToken, payload.jti)
    if row and row.revoked_at is None:
        row.revoked_at = utcnow()
        await session.commit()


async def revoke_all_sessions(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Used when banning a user. The caller commits."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def _issue(
    session: AsyncSession,
    user: User,
    settings: Settings,
    client: ClientInfo,
    *,
    family_id: uuid.UUID | None,
    rotated: RefreshToken | None = None,
) -> IssuedTokens:
    jti = uuid.uuid4()
    expires_at = utcnow() + timedelta(days=settings.jwt_refresh_ttl_days)
    family = family_id or uuid.uuid4()
    session.add(
        RefreshToken(
            id=jti,
            user_id=user.id,
            family_id=family,
            expires_at=expires_at,
            ip=client.ip,
            user_agent=(client.user_agent or "")[:300] or None,
        )
    )
    if rotated is not None:
        rotated.revoked_at = utcnow()
        rotated.replaced_by_id = jti
    return IssuedTokens(
        access=create_access_token(user.id, list(user.roles), settings),
        refresh=create_refresh_token(user.id, jti, family, expires_at, settings),
    )
