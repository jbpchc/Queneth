"""Admin view of the three external APIs: status, live probes, email log."""

import uuid
from contextlib import suppress
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound
from app.core.pagination import clamp_limit, decode_cursor, encode_cursor
from app.integrations.base import IntegrationError, IntegrationName, IntegrationState, registry
from app.integrations.brevo_email import BrevoAdapter
from app.integrations.cloudinary_client import CloudinaryAdapter
from app.integrations.psgc import PsgcAdapter, load_snapshot
from app.models.integration import EmailLog, GeoCache, MediaAsset
from app.schemas.notifications import IntegrationStatusOut

META = {
    IntegrationName.PSGC: (
        "PSGC API",
        "Region, province, city and barangay lists for addresses",
        "Bundled PSGC snapshot (then stale cache)",
    ),
    IntegrationName.CLOUDINARY: (
        "Cloudinary",
        "Signed image uploads, resizing and WebP/AVIF delivery",
        "Local disk storage served by the API",
    ),
    IntegrationName.BREVO: (
        "Brevo Transactional Email",
        "Verification, password reset, order and drop emails",
        "Queued with retries; copy kept in the in-app inbox",
    ),
}


def _configured(name: IntegrationName, settings: Settings) -> bool:
    if name is IntegrationName.CLOUDINARY:
        return settings.cloudinary_configured
    if name is IntegrationName.BREVO:
        return bool(settings.brevo_api_key)
    return True  # PSGC needs no key


def _health(state: IntegrationState, settings: Settings, configured: bool) -> str:
    if settings.integrations_mode == "mock":
        return "mock"
    if not configured:
        return "unconfigured"
    if state.last_error_at and (
        not state.last_success_at or state.last_error_at > state.last_success_at
    ):
        return "degraded"
    return "ok" if state.last_success_at else "idle"


async def statuses(session: AsyncSession, settings: Settings) -> list[IntegrationStatusOut]:
    email_counts = dict(
        (
            await session.execute(select(EmailLog.status, func.count()).group_by(EmailLog.status))
        ).all()
    )
    media_counts = dict(
        (
            await session.execute(
                select(MediaAsset.provider, func.count())
                .where(MediaAsset.status == "ready")
                .group_by(MediaAsset.provider)
            )
        ).all()
    )
    cached = await session.scalar(select(func.count()).select_from(GeoCache)) or 0
    details: dict[IntegrationName, dict[str, Any]] = {
        IntegrationName.PSGC: {
            "base_url": settings.psgc_base_url,
            "cached_lists": cached,
            "cache_days": settings.psgc_cache_days,
            "snapshot_date": load_snapshot().generated,
        },
        IntegrationName.CLOUDINARY: {
            "cloud_name": settings.cloudinary_cloud_name,
            "uploads_cloudinary": media_counts.get("cloudinary", 0),
            "uploads_local": media_counts.get("local", 0),
        },
        IntegrationName.BREVO: {
            "sender": settings.brevo_sender_email,
            "emails": {k: email_counts.get(k, 0) for k in ("queued", "sent", "mocked", "failed")},
        },
    }
    out = []
    for state in registry.all():
        configured = _configured(state.name, settings)
        label, purpose, fallback = META[state.name]
        out.append(
            IntegrationStatusOut(
                name=state.name.value,  # type: ignore[arg-type]
                label=label,
                purpose=purpose,
                mode=settings.integrations_mode,
                configured=configured,
                health=_health(state, settings, configured),  # type: ignore[arg-type]
                calls=state.calls,
                failures=state.failures,
                fallbacks=state.fallbacks,
                last_success_at=state.last_success_at,
                last_error_at=state.last_error_at,
                last_error=state.last_error,
                last_latency_ms=state.last_latency_ms,
                last_fallback_at=state.last_fallback_at,
                fallback=fallback,
                details=details[state.name],
            )
        )
    return out


async def probe(name: IntegrationName, settings: Settings) -> None:
    """Make one real call so the admin can see whether the API answers now.
    In mock mode nothing leaves the server."""
    if settings.integrations_mode == "mock":
        raise Conflict(
            "Integrations are in mock mode; switch INTEGRATIONS_MODE=live to probe.",
            code="mock_mode",
        )
    adapter = {
        IntegrationName.PSGC: PsgcAdapter,
        IntegrationName.CLOUDINARY: CloudinaryAdapter,
        IntegrationName.BREVO: BrevoAdapter,
    }[name](settings)
    # Failures are recorded in the registry; the page shows them.
    with suppress(IntegrationError):
        await adapter.ping()


async def list_emails(
    session: AsyncSession,
    *,
    cursor: str | None,
    limit: int | None,
    status: str | None,
    template: str | None,
    to_email: str | None,
) -> tuple[list[EmailLog], str | None]:
    size = clamp_limit(limit)
    stmt = select(EmailLog).order_by(EmailLog.created_at.desc(), EmailLog.id.desc())
    if status:
        stmt = stmt.where(EmailLog.status == status)
    if template:
        stmt = stmt.where(EmailLog.template == template)
    if to_email:
        stmt = stmt.where(EmailLog.to_email == to_email.strip().lower())
    if pos := decode_cursor(cursor):
        created, last_id = datetime.fromisoformat(pos["created_at"]), uuid.UUID(pos["id"])
        stmt = stmt.where(
            (EmailLog.created_at < created)
            | ((EmailLog.created_at == created) & (EmailLog.id < last_id))
        )
    rows = list((await session.scalars(stmt.limit(size + 1))).all())
    next_cursor = None
    if len(rows) > size:
        rows = rows[:size]
        next_cursor = encode_cursor(
            {"created_at": rows[-1].created_at.isoformat(), "id": str(rows[-1].id)}
        )
    return rows, next_cursor


async def preview(session: AsyncSession, email_id: uuid.UUID) -> EmailLog:
    entry = await session.get(EmailLog, email_id)
    if entry is None:
        raise NotFound("We couldn't find that email.")
    # Real emails may hold live reset links: only mocked ones (never delivered
    # to a mailbox) can be opened here, for demos without a Brevo key.
    if entry.status != "mocked":
        raise Conflict("Only mock-mode emails can be previewed.", code="preview_unavailable")
    return entry
