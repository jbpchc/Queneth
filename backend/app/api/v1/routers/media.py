import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.core.rate_limit import UPLOAD_LIMIT, limiter
from app.schemas.media import CloudinaryResult, MediaAssetOut, UploadRequest, UploadTicket
from app.services.media_service import MediaService

router = APIRouter(prefix="/media", tags=["media"])


def get_media_service(session: DbSession, settings: AppSettings) -> MediaService:
    return MediaService(session, settings)


@router.post(
    "/uploads",
    response_model=UploadTicket,
    status_code=status.HTTP_201_CREATED,
    summary="Validate an image and get a signed upload ticket",
)
@limiter.limit(UPLOAD_LIMIT)
async def create_upload(
    request: Request,
    body: UploadRequest,
    user: CurrentUser,
    media: MediaService = Depends(get_media_service),
) -> UploadTicket:
    # Permission depends on purpose (product/boutique: sellers & admins; avatar/review: shoppers).
    return await media.create_ticket(user, body)


@router.post(
    "/uploads/{asset_id}/complete",
    response_model=MediaAssetOut,
    summary="Confirm a Cloudinary upload (response signature is verified)",
)
async def complete_upload(
    asset_id: uuid.UUID,
    body: CloudinaryResult,
    user: CurrentUser,
    media: MediaService = Depends(get_media_service),
) -> MediaAssetOut:
    return media.to_out(await media.complete_cloudinary(user, asset_id, body))


@router.post(
    "/uploads/{asset_id}/fallback",
    response_model=UploadTicket,
    summary="Cloudinary unreachable from the browser: switch to local storage",
)
async def fallback_upload(
    asset_id: uuid.UUID, user: CurrentUser, media: MediaService = Depends(get_media_service)
) -> UploadTicket:
    return await media.fallback_ticket(user, asset_id)


@router.post(
    "/uploads/{asset_id}/file",
    response_model=MediaAssetOut,
    summary="Local-storage upload target (mock mode / fallback)",
)
async def local_upload(
    asset_id: uuid.UUID,
    user: CurrentUser,
    ticket: str = Form(...),
    file: UploadFile = File(...),
    media: MediaService = Depends(get_media_service),
) -> MediaAssetOut:
    return media.to_out(await media.receive_local(user, asset_id, ticket, file))
