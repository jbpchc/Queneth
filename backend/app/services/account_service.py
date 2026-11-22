"""Email verification and password reset (single-use, hashed, expiring tokens)."""

import hashlib
import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlencode

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, ValidationFailed
from app.core.security import as_aware, hash_password, utcnow
from app.models.integration import EmailLog
from app.models.user import EmailToken, User
from app.services import auth_service, email_service, email_templates

VERIFY = "verify_email"
RESET = "reset_password"
TTL = {VERIFY: timedelta(hours=48), RESET: timedelta(hours=1)}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _issue_token(session: AsyncSession, user: User, purpose: str) -> str:
    # Only the newest link of each kind works: retire older unused ones.
    await session.execute(
        update(EmailToken)
        .where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    raw = secrets.token_urlsafe(32)
    session.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=_hash(raw),
            expires_at=utcnow() + TTL[purpose],
        )
    )
    return raw


async def _consume(session: AsyncSession, raw: str, purpose: str) -> EmailToken:
    row = await session.scalar(
        select(EmailToken).where(EmailToken.token_hash == _hash(raw)).with_for_update()
    )
    if row is None or row.purpose != purpose or row.used_at is not None:
        raise ValidationFailed("This link is invalid or was already used.", code="invalid_token")
    if as_aware(row.expires_at) <= utcnow():
        raise ValidationFailed("This link has expired. Request a new one.", code="token_expired")
    row.used_at = utcnow()
    return row


def _link(settings: Settings, path: str, token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}{path}?{urlencode({'token': token})}"


async def send_verification(session: AsyncSession, user: User, settings: Settings) -> EmailLog:
    """Queue a verification email. The caller commits, then schedules delivery."""
    if user.email_verified_at is not None:
        raise Conflict("Your email is already confirmed.", code="already_verified")
    raw = await _issue_token(session, user, VERIFY)
    rendered = email_templates.verify_email(
        name=user.name, url=_link(settings, "/verify-email", raw)
    )
    return email_service.queue(session, user=user, to_email=user.email, email=rendered)


async def verify_email(session: AsyncSession, raw: str) -> User:
    token = await _consume(session, raw, VERIFY)
    user = await session.get(User, token.user_id)
    assert user is not None
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    await session.commit()
    return user


async def request_password_reset(
    session: AsyncSession, email: str, settings: Settings
) -> EmailLog | None:
    """Always "succeeds" for the caller (no account enumeration). Returns the
    queued email when the account exists, so the router can deliver it."""
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or user.is_banned:
        return None
    raw = await _issue_token(session, user, RESET)
    rendered = email_templates.password_reset(
        name=user.name, url=_link(settings, "/reset-password", raw)
    )
    entry = email_service.queue(session, user=user, to_email=user.email, email=rendered)
    await session.commit()
    return entry


async def reset_password(
    session: AsyncSession, raw: str, new_password: str, settings: Settings
) -> tuple[User, uuid.UUID]:
    """Set a new password, sign out every device, and send a confirmation."""
    token = await _consume(session, raw, RESET)
    user = await session.get(User, token.user_id)
    assert user is not None
    user.password_hash = hash_password(new_password)
    # Clicking the emailed link proves mailbox ownership.
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    await auth_service.revoke_all_sessions(session, user.id)
    entry = email_service.queue(
        session,
        user=user,
        to_email=user.email,
        email=email_templates.password_changed(
            name=user.name, url=f"{settings.frontend_url.rstrip('/')}/login"
        ),
    )
    await session.commit()
    return user, entry.id
