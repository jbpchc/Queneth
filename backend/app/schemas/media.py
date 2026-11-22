import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import ApiModel

MediaPurpose = Literal["product", "boutique", "review", "avatar"]
ImageType = Literal["image/jpeg", "image/png", "image/webp"]


class UploadRequest(ApiModel):
    purpose: MediaPurpose
    filename: str = Field(max_length=200, examples=["silk-slip-front.jpg"])
    content_type: ImageType
    size_bytes: int = Field(gt=0, examples=[842_113])

    @field_validator("content_type", mode="before")
    @classmethod
    def _normalise_type(cls, v: object) -> object:
        # Postel's Law: "IMAGE/JPG" and "image/jpg" mean JPEG.
        if isinstance(v, str):
            v = v.strip().lower()
            return "image/jpeg" if v == "image/jpg" else v
        return v


class UploadTicket(ApiModel):
    """POST `fields` + the file (field name `file`) as multipart to `upload_url`."""

    asset_id: uuid.UUID
    provider: Literal["cloudinary", "local"]
    upload_url: str
    fields: dict[str, str]
    public_id: str
    max_bytes: int


class CloudinaryResult(ApiModel):
    """The JSON Cloudinary returns from an upload; its signature is verified."""

    public_id: str
    version: int
    signature: str
    secure_url: str
    width: int | None = None
    height: int | None = None
    format: str | None = None
    bytes: int | None = None


class MediaAssetOut(ApiModel):
    id: uuid.UUID
    purpose: str
    provider: str
    status: str
    url: str | None
    thumbnail_url: str | None
    width: int | None
    height: int | None
    format: str | None
    bytes: int | None
    created_at: datetime
