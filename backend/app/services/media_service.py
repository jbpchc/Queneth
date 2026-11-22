"""Image uploads: signed Cloudinary uploads, with local disk as the fallback.

Flow (the browser does the same thing for both providers):
1. POST /media/uploads           → validate type + size, create a pending asset,
                                    return an UploadTicket (url + form fields)
2. browser POSTs file + fields   → Cloudinary, or this API's local endpoint
3. (Cloudinary only) POST /media/uploads/{id}/complete with Cloudinary's JSON
                                 → response signature verified, asset ready

If Cloudinary is in mock mode, unconfigured, or fails in the browser, the
ticket is local: bytes are sniffed, size-checked and written to LOCAL_UPLOAD_DIR.
"""

import uuid
from datetime import timedelta
from pathlib import PurePosixPath

import jwt
import structlog
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.core.permissions import Permission, assert_can
from app.core.security import JWT_ALGORITHM, utcnow
from app.integrations.base import IntegrationName, registry
from app.integrations.cloudinary_client import THUMBNAIL, CloudinaryAdapter
from app.integrations.image_sniff import sniff
from app.models.integration import MediaAsset
from app.models.user import User
from app.schemas.media import CloudinaryResult, MediaAssetOut, UploadRequest, UploadTicket

log = structlog.get_logger(__name__)

#: Product and boutique images are studio tools; avatars and review photos
#: belong to any signed-in shopper.
PURPOSE_PERMISSION = {
    "product": Permission.MEDIA_UPLOAD,
    "boutique": Permission.PROFILE_MANAGE,  # applicants upload a logo before approval
    "review": Permission.PROFILE_MANAGE,
    "avatar": Permission.PROFILE_MANAGE,
}
TICKET_TTL = timedelta(minutes=10)


class MediaService:
    def __init__(
        self, session: AsyncSession, settings: Settings, adapter: CloudinaryAdapter | None = None
    ):
        self.session = session
        self.settings = settings
        self.cloudinary = adapter or CloudinaryAdapter(settings)

    @property
    def use_cloudinary(self) -> bool:
        return not self.cloudinary.mock and self.cloudinary.configured

    async def create_ticket(self, user: User, req: UploadRequest) -> UploadTicket:
        assert_can(user, PURPOSE_PERMISSION[req.purpose])
        if req.size_bytes > self.settings.max_upload_bytes:
            raise ValidationFailed(
                "Images can be up to 5 MB.",
                code="file_too_large",
                details=[{"field": "size_bytes", "message": "Max 5 MB."}],
            )
        public_id = f"{self.settings.cloudinary_folder}/{req.purpose}/{uuid.uuid4().hex}"
        asset = MediaAsset(
            owner_id=user.id,
            purpose=req.purpose,
            provider="cloudinary" if self.use_cloudinary else "local",
            public_id=public_id,
            status="pending",
            content_type=req.content_type,
        )
        self.session.add(asset)
        await self.session.commit()
        if not self.use_cloudinary and not self.cloudinary.mock:
            registry.fallback(IntegrationName.CLOUDINARY)  # live mode but no credentials
        return self._ticket(asset)

    async def fallback_ticket(self, user: User, asset_id: uuid.UUID) -> UploadTicket:
        """Browser couldn't reach Cloudinary: switch this pending asset to local disk."""
        asset = await self._own_pending(user, asset_id)
        asset.provider = "local"
        await self.session.commit()
        registry.fallback(IntegrationName.CLOUDINARY)
        registry.failure(IntegrationName.CLOUDINARY, "browser upload to Cloudinary failed")
        log.warning("cloudinary_fallback", asset_id=str(asset.id))
        return self._ticket(asset)

    def _ticket(self, asset: MediaAsset) -> UploadTicket:
        if asset.provider == "cloudinary":
            fields = self.cloudinary.signed_upload_fields(
                asset.public_id, int(utcnow().timestamp())
            )
            url = self.cloudinary.upload_url
        else:
            token = jwt.encode(
                {
                    "type": "upload",
                    "aid": str(asset.id),
                    "uid": str(asset.owner_id),
                    "exp": utcnow() + TICKET_TTL,
                },
                self.settings.jwt_secret,
                algorithm=JWT_ALGORITHM,
            )
            fields = {"ticket": token}
            base = f"{self.settings.api_public_url}{self.settings.api_v1_prefix}"
            url = f"{base}/media/uploads/{asset.id}/file"
        return UploadTicket(
            asset_id=asset.id,
            provider=asset.provider,  # type: ignore[arg-type]
            upload_url=url,
            fields=fields,
            public_id=asset.public_id,
            max_bytes=self.settings.max_upload_bytes,
        )

    async def _own_pending(self, user: User, asset_id: uuid.UUID) -> MediaAsset:
        asset = await self.session.get(MediaAsset, asset_id)
        # Owner-scoped lookup: someone else's asset id looks exactly like a missing one.
        if asset is None or asset.owner_id != user.id:
            raise NotFound("We couldn't find that upload.")
        if asset.status != "pending":
            raise Conflict("That upload is already finished.", code="upload_finished")
        return asset

    async def complete_cloudinary(
        self, user: User, asset_id: uuid.UUID, result: CloudinaryResult
    ) -> MediaAsset:
        asset = await self._own_pending(user, asset_id)
        if asset.provider != "cloudinary" or result.public_id != asset.public_id:
            raise ValidationFailed("That upload doesn't match its ticket.", code="upload_mismatch")
        if not self.cloudinary.verify_upload(result.public_id, result.version, result.signature):
            raise PermissionDenied("Upload signature check failed.", code="bad_upload_signature")
        asset.status = "ready"
        asset.url = result.secure_url
        asset.width, asset.height = result.width, result.height
        asset.format, asset.bytes = result.format, result.bytes
        await self.session.commit()
        registry.success(IntegrationName.CLOUDINARY, 0)
        return asset

    async def receive_local(
        self, user: User, asset_id: uuid.UUID, ticket: str, file: UploadFile
    ) -> MediaAsset:
        try:
            claims = jwt.decode(ticket, self.settings.jwt_secret, algorithms=[JWT_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise PermissionDenied(
                "This upload link has expired.", code="bad_upload_ticket"
            ) from exc
        if (
            claims.get("type") != "upload"
            or claims.get("aid") != str(asset_id)
            or claims.get("uid") != str(user.id)
        ):
            raise PermissionDenied("This upload link isn't yours.", code="bad_upload_ticket")
        asset = await self._own_pending(user, asset_id)
        if asset.provider != "local":
            raise Conflict("This upload goes to Cloudinary.", code="wrong_provider")

        data = await file.read(self.settings.max_upload_bytes + 1)
        if len(data) > self.settings.max_upload_bytes:
            raise ValidationFailed("Images can be up to 5 MB.", code="file_too_large")
        info = sniff(data)
        if info is None:
            raise ValidationFailed("Upload a JPEG, PNG or WebP image.", code="unsupported_image")

        relative = PurePosixPath(f"{asset.public_id}.{info.ext}")
        target = self.settings.upload_dir.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        asset.status = "ready"
        asset.content_type = info.content_type
        asset.format = info.ext
        asset.bytes = len(data)
        asset.width, asset.height = info.width, info.height
        asset.url = (
            f"{self.settings.api_public_url}{self.settings.api_v1_prefix}/media/files/{relative}"
        )
        await self.session.commit()
        return asset

    async def get_ready_asset(self, user: User, asset_id: uuid.UUID, purpose: str) -> MediaAsset:
        asset = await self.session.get(MediaAsset, asset_id)
        if asset is None or asset.owner_id != user.id or asset.status != "ready":
            raise NotFound("We couldn't find that image.", code="asset_not_found")
        if asset.purpose != purpose:
            raise ValidationFailed(
                f"That image wasn't uploaded as a {purpose}.", code="wrong_purpose"
            )
        return asset

    def to_out(self, asset: MediaAsset) -> MediaAssetOut:
        thumb = asset.url
        if asset.provider == "cloudinary" and asset.status == "ready":
            thumb = self.cloudinary.delivery_url(asset.public_id, THUMBNAIL)
        return MediaAssetOut(
            id=asset.id,
            purpose=asset.purpose,
            provider=asset.provider,
            status=asset.status,
            url=asset.url,
            thumbnail_url=thumb,
            width=asset.width,
            height=asset.height,
            format=asset.format,
            bytes=asset.bytes,
            created_at=asset.created_at,
        )
