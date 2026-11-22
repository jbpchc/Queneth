"""Transactional email: queue → deliver → retry, mirrored to the in-app inbox.

`queue()` writes an EmailLog (status `queued`) and, for registered users, a
Notification, in the caller's transaction. Delivery happens afterwards in a
FastAPI BackgroundTask; failures are retried by the APScheduler job with
exponential backoff until EMAIL_MAX_ATTEMPTS, then marked `failed`.

Mock mode (INTEGRATIONS_MODE=mock) never calls Brevo: emails are marked
`mocked` and can be previewed by admins in the "Sent emails" log.
"""

import uuid
from collections.abc import Callable
from datetime import timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import utcnow
from app.integrations.base import IntegrationError, IntegrationName, registry
from app.integrations.brevo_email import BrevoAdapter, OutgoingEmail
from app.models.integration import EmailLog, Notification
from app.models.user import User
from app.services.email_templates import RenderedEmail

log = structlog.get_logger(__name__)

SessionFactory = Callable[[], AsyncSession]


def queue(
    session: AsyncSession, *, user: User | None, to_email: str, email: RenderedEmail
) -> EmailLog:
    """Stage an email (and its inbox copy) in the current transaction."""
    entry = EmailLog(
        id=uuid.uuid4(),
        to_email=to_email,
        to_name=user.name if user else None,
        user_id=user.id if user else None,
        template=email.template,
        subject=email.subject,
        html=email.html,
        text=email.text,
        status="queued",
        attempts=0,
        next_attempt_at=utcnow(),
    )
    session.add(entry)
    if user is not None:
        session.add(
            Notification(
                user_id=user.id,
                type=f"email.{email.template}",
                payload={
                    "title": email.inbox_title,
                    "body": email.inbox_body,
                    "action_url": email.inbox_action_url,
                },
            )
        )
    return entry


def _backoff(attempts: int) -> timedelta:
    return timedelta(minutes=min(2**attempts, 60))


async def deliver(
    session_factory: SessionFactory,
    log_id: uuid.UUID,
    settings: Settings,
    adapter: BrevoAdapter | None = None,
) -> str:
    """Try to send one queued email. Safe to call twice: finished emails are skipped."""
    brevo = adapter or BrevoAdapter(settings)
    async with session_factory() as session:
        entry = await session.get(EmailLog, log_id, with_for_update=True)
        if entry is None or entry.status in {"sent", "mocked"}:
            return entry.status if entry else "missing"
        entry.attempts += 1
        if brevo.mock:
            entry.status, entry.sent_at, entry.last_error = "mocked", utcnow(), None
            log.info("email_mocked", template=entry.template, email_id=str(entry.id))
        else:
            try:
                message_id = await brevo.send(
                    OutgoingEmail(
                        to_email=entry.to_email,
                        to_name=entry.to_name,
                        subject=entry.subject,
                        html=entry.html,
                        text=entry.text,
                        tags=[entry.template],
                    )
                )
            except IntegrationError as exc:
                registry.fallback(IntegrationName.BREVO)  # the inbox copy still stands
                entry.last_error = str(exc)[:300]
                if entry.attempts >= settings.email_max_attempts:
                    entry.status, entry.next_attempt_at = "failed", None
                else:
                    entry.status, entry.next_attempt_at = (
                        "queued",
                        utcnow() + _backoff(entry.attempts),
                    )
                log.warning("email_failed", email_id=str(entry.id), attempts=entry.attempts)
            else:
                entry.status, entry.sent_at = "sent", utcnow()
                entry.provider_message_id, entry.last_error = message_id, None
        status = entry.status
        await session.commit()
        return status


async def retry_due(session_factory: SessionFactory, settings: Settings, limit: int = 20) -> int:
    """Scheduler job: deliver queued emails whose backoff has elapsed."""
    async with session_factory() as session:
        ids = list(
            (
                await session.scalars(
                    select(EmailLog.id)
                    .where(EmailLog.status == "queued", EmailLog.next_attempt_at <= utcnow())
                    .order_by(EmailLog.next_attempt_at)
                    .limit(limit)
                )
            ).all()
        )
    for log_id in ids:
        await deliver(session_factory, log_id, settings)
    return len(ids)


async def requeue(session: AsyncSession, log_id: uuid.UUID) -> EmailLog | None:
    """Admin action: put a failed email back in the queue."""
    entry = await session.get(EmailLog, log_id)
    if entry is None:
        return None
    if entry.status == "failed":
        entry.status, entry.attempts, entry.next_attempt_at = "queued", 0, utcnow()
        await session.commit()
    return entry
