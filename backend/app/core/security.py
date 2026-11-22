"""Password hashing, JWTs and auth cookies.

- Passwords: Argon2id via pwdlib.
- Access token: 15 min JWT in an httpOnly cookie (path /).
- Refresh token: 7 day JWT in an httpOnly cookie scoped to /api/v1/auth, rotated
  on every use and tracked server-side (see RefreshToken).
- CSRF: double-submit token in a readable cookie, echoed in X-CSRF-Token.
- Session hint: a readable, non-sensitive cookie carrying only the role names,
  so the Next.js proxy can redirect signed-out users (UX only; never trusted).
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from fastapi import Response
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import Settings
from app.core.errors import NotAuthenticated

ACCESS_COOKIE = "qn_access"
REFRESH_COOKIE = "qn_refresh"
CSRF_COOKIE = "qn_csrf"
SESSION_HINT_COOKIE = "qn_session"
CSRF_HEADER = "X-CSRF-Token"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "queneth-api"

_hasher = PasswordHash((Argon2Hasher(),))
# Verified against when the email is unknown, so response time doesn't reveal
# whether an account exists.
_DUMMY_HASH = _hasher.hash("queneth-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    try:
        return _hasher.verify(password, password_hash)
    except Exception:  # noqa: BLE001 — malformed hash counts as a mismatch
        return False


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_aware(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@dataclass(frozen=True)
class TokenPayload:
    sub: uuid.UUID
    jti: uuid.UUID
    type: Literal["access", "refresh"]
    exp: datetime
    family: uuid.UUID | None = None


def _encode(claims: dict[str, Any], settings: Settings) -> str:
    return jwt.encode(claims, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID, roles: list[str], settings: Settings) -> str:
    now = utcnow()
    return _encode(
        {
            "sub": str(user_id),
            "roles": roles,
            "type": "access",
            "jti": uuid.uuid4().hex,
            "iss": JWT_ISSUER,
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_access_ttl_minutes),
        },
        settings,
    )


def create_refresh_token(
    user_id: uuid.UUID,
    jti: uuid.UUID,
    family_id: uuid.UUID,
    expires_at: datetime,
    settings: Settings,
) -> str:
    return _encode(
        {
            "sub": str(user_id),
            "type": "refresh",
            "jti": str(jti),
            "fam": str(family_id),
            "iss": JWT_ISSUER,
            "iat": utcnow(),
            "exp": expires_at,
        },
        settings,
    )


def decode_token(
    token: str, expected: Literal["access", "refresh"], settings: Settings
) -> TokenPayload:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "sub", "type", "jti"]},
        )
        if claims["type"] != expected:
            raise jwt.InvalidTokenError("wrong token type")
        return TokenPayload(
            sub=uuid.UUID(claims["sub"]),
            jti=uuid.UUID(claims["jti"]),
            type=claims["type"],
            exp=datetime.fromtimestamp(claims["exp"], UTC),
            family=uuid.UUID(claims["fam"]) if claims.get("fam") else None,
        )
    except jwt.ExpiredSignatureError as exc:
        raise NotAuthenticated(
            "Your session has expired. Please sign in again.", code="token_expired"
        ) from exc
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise NotAuthenticated(code="invalid_token") from exc


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _cookie_kwargs(settings: Settings) -> dict[str, Any]:
    return {"secure": settings.cookie_secure, "samesite": "lax", "domain": settings.cookie_domain}


def set_auth_cookies(
    response: Response, *, access: str, refresh: str, roles: list[str], settings: Settings
) -> None:
    common = _cookie_kwargs(settings)
    access_age = settings.jwt_access_ttl_minutes * 60
    refresh_age = settings.jwt_refresh_ttl_days * 86_400
    response.set_cookie(
        ACCESS_COOKIE, access, max_age=access_age, httponly=True, path="/", **common
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=refresh_age,
        httponly=True,
        path=f"{settings.api_v1_prefix}/auth",
        **common,
    )
    response.set_cookie(
        CSRF_COOKIE, new_csrf_token(), max_age=refresh_age, httponly=False, path="/", **common
    )
    response.set_cookie(
        SESSION_HINT_COOKIE,
        ".".join(sorted(roles)),
        max_age=refresh_age,
        httponly=False,
        path="/",
        **common,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    domain = settings.cookie_domain
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=domain)
    response.delete_cookie(REFRESH_COOKIE, path=f"{settings.api_v1_prefix}/auth", domain=domain)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=domain)
    response.delete_cookie(SESSION_HINT_COOKIE, path="/", domain=domain)
