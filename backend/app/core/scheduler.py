"""APScheduler jobs (spec §3): email retries (Phase 3) and escrow auto-release
7 days after delivery (Phase 7), and drop go-live notifications (Phase 8)."""

from collections.abc import Callable

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services import email_service, fulfilment_service, promotion_service, studio_service

log = structlog.get_logger(__name__)


def build_scheduler(
    session_factory: Callable[[], AsyncSession], settings: Settings
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    async def retry_emails() -> None:
        try:
            sent = await email_service.retry_due(session_factory, settings)
            if sent:
                log.info("email_retry_batch", count=sent)
        except Exception:  # noqa: BLE001 — a failed tick must not kill the scheduler
            log.exception("email_retry_job_failed")

    scheduler.add_job(
        retry_emails, "interval", seconds=60, id="email_retry", max_instances=1, coalesce=True
    )

    async def release_escrow() -> None:
        try:
            async with session_factory() as session:
                done = await fulfilment_service.release_due(session, settings)
            if done:
                log.info("escrow_auto_release", count=done)
        except Exception:  # noqa: BLE001 — a failed tick must not kill the scheduler
            log.exception("escrow_auto_release_failed")

    scheduler.add_job(
        release_escrow, "interval", minutes=15, id="escrow_release", max_instances=1, coalesce=True
    )

    async def drop_golive() -> None:
        try:
            async with session_factory() as session:
                sent = await studio_service.notify_live_drops(session, settings)
            if sent:
                log.info("drop_golive_notified", count=sent)
        except Exception:  # noqa: BLE001
            log.exception("drop_golive_failed")

    scheduler.add_job(
        drop_golive, "interval", seconds=60, id="drop_golive", max_instances=1, coalesce=True
    )

    async def promotions_sweep() -> None:
        try:
            async with session_factory() as session:
                done = await promotion_service.sweep(session)
            if any(done.values()):
                log.info("promotions_sweep", **done)
        except Exception:  # noqa: BLE001
            log.exception("promotions_sweep_failed")

    scheduler.add_job(
        promotions_sweep, "interval", seconds=60, id="promotions", max_instances=1, coalesce=True
    )
    return scheduler
