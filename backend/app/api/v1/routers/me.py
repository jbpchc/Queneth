from fastapi import APIRouter, Depends

from app.api.deps import AppSettings, DbSession, require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.auth import MeOut, MeUpdate
from app.services import user_service

router = APIRouter(prefix="/me", tags=["me"])

ProfileUser = Depends(require_permission(Permission.PROFILE_MANAGE))


@router.get("", response_model=MeOut, summary="The signed-in user and their permissions")
async def get_me(user: User = ProfileUser) -> MeOut:
    return user_service.to_me(user)


@router.patch("", response_model=MeOut, summary="Update your profile")
async def update_me(
    body: MeUpdate, session: DbSession, settings: AppSettings, user: User = ProfileUser
) -> MeOut:
    updated = await user_service.update_profile(session, user, body, settings)
    return user_service.to_me(updated)
