"""Admin Control Room endpoints. Phase 2 ships role and ban management plus the
audit log; Phase 9 adds the rest of the Control Room."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import select

from app.api.deps import (
    AppSettings,
    DbSession,
    SessionFactoryDep,
    client_ip,
    require_permission,
    require_role,
)
from app.core.errors import NotFound
from app.core.permissions import Permission, Role
from app.integrations.base import IntegrationName
from app.models.user import User
from app.schemas.admin import AdminUserOut, AuditLogOut, RoleUpdate, StatusUpdate
from app.schemas.commerce import ReleaseResult, TransitionRequest
from app.schemas.common import CursorPage
from app.schemas.notifications import EmailLogOut, EmailPreview, IntegrationStatusOut
from app.schemas.studio import Decision, SellerApplicationOut
from app.services import (
    audit_service,
    boutique_service,
    email_service,
    fulfilment_service,
    integration_service,
    user_service,
)
from app.services.catalog_service import CatalogService

# Every route below requires the ADMIN role; each also declares its permission.
router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_role(Role.ADMIN))]
)


def _admin_user(user: User) -> AdminUserOut:
    me = user_service.to_me(user)
    return AdminUserOut(**me.model_dump(exclude={"permissions"}), last_login_at=user.last_login_at)


@router.patch(
    "/users/{user_id}/roles", response_model=AdminUserOut, summary="Change a user's roles"
)
async def change_roles(
    user_id: uuid.UUID,
    body: RoleUpdate,
    request: Request,
    session: DbSession,
    actor: User = Depends(require_permission(Permission.USER_MANAGE_ROLES)),
) -> AdminUserOut:
    user = await user_service.set_roles(session, actor, user_id, body, client_ip(request))
    return _admin_user(user)


@router.patch("/users/{user_id}/status", response_model=AdminUserOut, summary="Ban or unban a user")
async def change_status(
    user_id: uuid.UUID,
    body: StatusUpdate,
    request: Request,
    session: DbSession,
    actor: User = Depends(require_permission(Permission.USER_BAN)),
) -> AdminUserOut:
    user = await user_service.set_status(session, actor, user_id, body, client_ip(request))
    return _admin_user(user)


@router.get("/audit", response_model=CursorPage[AuditLogOut], summary="Audit log, newest first")
async def audit_log(
    session: DbSession,
    _: User = Depends(require_permission(Permission.AUDIT_VIEW)),
    cursor: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=96),
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
) -> CursorPage[AuditLogOut]:
    rows, next_cursor = await audit_service.list_entries(
        session,
        cursor=cursor,
        limit=limit,
        action=action,
        target_type=target_type,
        target_id=target_id,
    )
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    actors = (
        {
            u.id: f"{u.name} <{u.email}>"
            for u in (await session.scalars(select(User).where(User.id.in_(actor_ids)))).all()
        }
        if actor_ids
        else {}
    )
    return CursorPage[AuditLogOut](
        items=[
            AuditLogOut.model_validate(r).model_copy(update={"actor": actors.get(r.actor_id)})
            for r in rows
        ],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.get(
    "/integrations",
    response_model=list[IntegrationStatusOut],
    summary="Status of PSGC, Cloudinary and Brevo (mode, last success, last error)",
)
async def integrations(
    session: DbSession,
    settings: AppSettings,
    _: User = Depends(require_permission(Permission.INTEGRATIONS_VIEW)),
) -> list[IntegrationStatusOut]:
    return await integration_service.statuses(session, settings)


@router.post(
    "/integrations/{name}/check",
    response_model=list[IntegrationStatusOut],
    summary="Probe one external API now (live mode only)",
)
async def check_integration(
    name: IntegrationName,
    request: Request,
    session: DbSession,
    settings: AppSettings,
    actor: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
) -> list[IntegrationStatusOut]:
    await integration_service.probe(name, settings)
    audit_service.record(
        session,
        actor_id=actor.id,
        action="integration.checked",
        target_type="integration",
        target_id=name.value,
        ip=client_ip(request),
    )
    await session.commit()
    return await integration_service.statuses(session, settings)


@router.get("/emails", response_model=CursorPage[EmailLogOut], summary="Sent emails log")
async def emails(
    session: DbSession,
    _: User = Depends(require_permission(Permission.INTEGRATIONS_VIEW)),
    cursor: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=96),
    status: str | None = Query(default=None, pattern="^(queued|sent|mocked|failed)$"),
    template: str | None = None,
    to: str | None = None,
) -> CursorPage[EmailLogOut]:
    rows, next_cursor = await integration_service.list_emails(
        session, cursor=cursor, limit=limit, status=status, template=template, to_email=to
    )
    return CursorPage[EmailLogOut](
        items=[EmailLogOut.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
    )


@router.get(
    "/emails/{email_id}/preview",
    response_model=EmailPreview,
    summary="Open a mock-mode email (never available for real deliveries)",
)
async def email_preview(
    email_id: uuid.UUID,
    session: DbSession,
    _: User = Depends(require_permission(Permission.INTEGRATIONS_VIEW)),
) -> EmailPreview:
    entry = await integration_service.preview(session, email_id)
    return EmailPreview(subject=entry.subject, html=entry.html, text=entry.text)


@router.post(
    "/emails/{email_id}/retry", response_model=EmailLogOut, summary="Re-queue a failed email"
)
async def retry_email(
    email_id: uuid.UUID,
    request: Request,
    session: DbSession,
    settings: AppSettings,
    background: BackgroundTasks,
    session_factory: SessionFactoryDep,
    actor: User = Depends(require_permission(Permission.INTEGRATIONS_MANAGE)),
) -> EmailLogOut:
    entry = await email_service.requeue(session, email_id)
    if entry is None:
        raise NotFound("We couldn't find that email.")
    audit_service.record(
        session,
        actor_id=actor.id,
        action="email.retried",
        target_type="email",
        target_id=email_id,
        ip=client_ip(request),
    )
    await session.commit()
    background.add_task(email_service.deliver, session_factory, email_id, settings)
    return EmailLogOut.model_validate(entry)


# ─── Orders (override + escrow release) ────────────────────────────────────


@router.post(
    "/orders/{sub_id}/status",
    response_model=ReleaseResult,
    summary="Override a sub-order's status (audit-logged)",
)
async def override_order(
    sub_id: uuid.UUID,
    body: TransitionRequest,
    request: Request,
    background: BackgroundTasks,
    session: DbSession,
    settings: AppSettings,
    session_factory: SessionFactoryDep,
    admin: User = Depends(require_permission(Permission.ORDER_OVERRIDE)),
) -> ReleaseResult:
    moved = await fulfilment_service.transition(
        session,
        settings,
        admin,
        sub_id,
        body.to,
        note=body.note,
        tracking_no=body.tracking_no,
        reason=body.note,
    )
    if moved.changed:
        audit_service.record(
            session,
            actor_id=admin.id,
            action="order.override",
            target_type="sub_order",
            target_id=sub_id,
            after={"status": body.to, "note": body.note},
            ip=client_ip(request),
        )
        await session.commit()
    for email in moved.emails:
        background.add_task(email_service.deliver, session_factory, email.id, settings)
    return ReleaseResult(released=int(moved.changed))


@router.post(
    "/orders/release-due",
    response_model=ReleaseResult,
    summary="Release escrow for delivered orders (fast_forward=true skips the 7-day wait)",
)
async def release_due(
    request: Request,
    session: DbSession,
    settings: AppSettings,
    fast_forward: bool = False,
    admin: User = Depends(require_permission(Permission.ORDER_OVERRIDE)),
) -> ReleaseResult:
    released = await fulfilment_service.release_due(
        session,
        settings,
        older_than=timedelta(0) if fast_forward else fulfilment_service.AUTO_RELEASE_AFTER,
    )
    audit_service.record(
        session,
        actor_id=admin.id,
        action="escrow.release_due",
        target_type="sub_order",
        target_id="*",
        after={"released": released, "fast_forward": fast_forward},
        ip=client_ip(request),
    )
    await session.commit()
    return ReleaseResult(released=released)


# ─── Seller applications (the Control Room screen arrives in Phase 9) ──────


@router.get(
    "/sellers/pending",
    response_model=list[SellerApplicationOut],
    summary="Boutique applications waiting for a decision",
)
async def pending_sellers(
    session: DbSession,
    settings: AppSettings,
    admin: User = Depends(require_permission(Permission.SELLER_APPROVE)),
) -> list[SellerApplicationOut]:
    abs_url = CatalogService(session, settings).abs_url
    return [
        boutique_service.application_out(p, abs_url)
        for p in await boutique_service.pending(session, admin)
    ]


@router.post(
    "/sellers/{seller_id}/approve",
    response_model=SellerApplicationOut,
    summary="Approve a boutique (grants the SELLER role; audit-logged)",
)
async def approve_seller(
    seller_id: uuid.UUID,
    request: Request,
    background: BackgroundTasks,
    session: DbSession,
    settings: AppSettings,
    session_factory: SessionFactoryDep,
    admin: User = Depends(require_permission(Permission.SELLER_APPROVE)),
) -> SellerApplicationOut:
    profile, email = await boutique_service.decide(
        session, settings, admin, seller_id, True, None, client_ip(request)
    )
    background.add_task(email_service.deliver, session_factory, email.id, settings)
    return boutique_service.application_out(profile, CatalogService(session, settings).abs_url)


@router.post(
    "/sellers/{seller_id}/reject",
    response_model=SellerApplicationOut,
    summary="Reject a boutique application with a reason (audit-logged)",
)
async def reject_seller(
    seller_id: uuid.UUID,
    body: Decision,
    request: Request,
    background: BackgroundTasks,
    session: DbSession,
    settings: AppSettings,
    session_factory: SessionFactoryDep,
    admin: User = Depends(require_permission(Permission.SELLER_APPROVE)),
) -> SellerApplicationOut:
    profile, email = await boutique_service.decide(
        session, settings, admin, seller_id, False, body.reason, client_ip(request)
    )
    background.add_task(email_service.deliver, session_factory, email.id, settings)
    return boutique_service.application_out(profile, CatalogService(session, settings).abs_url)
