"""Profile updates and admin user management (roles, bans)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound
from app.core.permissions import Permission, Role, assert_can, permissions_for
from app.models.user import User, UserStatus
from app.schemas.admin import RoleUpdate, StatusUpdate
from app.schemas.auth import MeOut, MeUpdate
from app.services import audit_service, auth_service
from app.services.media_service import MediaService


def to_me(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        name=user.name,
        email=user.email,
        roles=list(user.roles),  # type: ignore[arg-type]
        avatar_url=user.avatar_url,
        status=user.status,  # type: ignore[arg-type]
        tier=user.tier,
        que_points=user.que_points,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at,
        permissions=sorted(str(p) for p in permissions_for(user)),
    )


async def update_profile(
    session: AsyncSession, user: User, data: MeUpdate, settings: Settings
) -> User:
    # Self-scoped by construction: the router only ever passes the signed-in user.
    assert_can(user, Permission.PROFILE_MANAGE)
    if data.name is not None:
        user.name = data.name
    if data.clear_avatar:
        user.avatar_url = None
    elif data.avatar_asset_id is not None:
        # Only the user's own, finished, avatar-purpose upload is accepted.
        media = MediaService(session, settings)
        asset = await media.get_ready_asset(user, data.avatar_asset_id, "avatar")
        user.avatar_url = media.to_out(asset).thumbnail_url
    await session.commit()
    await session.refresh(user)
    return user


async def _get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("We couldn't find that user.")
    return user


async def set_roles(
    session: AsyncSession, actor: User, user_id: uuid.UUID, data: RoleUpdate, ip: str | None
) -> User:
    """Replace a user's BUYER/SELLER roles. ADMIN is preserved untouched: it is
    seeded only and can't be granted or removed through the API."""
    assert_can(actor, Permission.USER_MANAGE_ROLES)
    target = await _get_user(session, user_id)
    before = sorted(target.roles)
    keep_admin = [Role.ADMIN.value] if target.has_role(Role.ADMIN) else []
    after = sorted(set(data.roles) | set(keep_admin))
    if after == before:
        return target
    target.roles = after
    audit_service.record(
        session,
        actor_id=actor.id,
        action="user.roles_changed",
        target_type="user",
        target_id=target.id,
        before={"roles": before},
        after={"roles": after},
        reason=data.reason,
        ip=ip,
    )
    await session.commit()
    await session.refresh(target)
    return target


async def set_status(
    session: AsyncSession, actor: User, user_id: uuid.UUID, data: StatusUpdate, ip: str | None
) -> User:
    assert_can(actor, Permission.USER_BAN)
    target = await _get_user(session, user_id)
    if target.id == actor.id:
        raise Conflict("You can't change your own account status.", code="cannot_target_self")
    if target.has_role(Role.ADMIN):
        raise Conflict("Admin accounts can't be banned from the panel.", code="cannot_ban_admin")
    before = target.status
    if before == data.status:
        return target
    target.status = data.status
    if data.status == UserStatus.BANNED.value:
        await auth_service.revoke_all_sessions(session, target.id)
    audit_service.record(
        session,
        actor_id=actor.id,
        action="user.banned" if data.status == UserStatus.BANNED.value else "user.unbanned",
        target_type="user",
        target_id=target.id,
        before={"status": before},
        after={"status": data.status},
        reason=data.reason,
        ip=ip,
    )
    await session.commit()
    await session.refresh(target)
    return target
