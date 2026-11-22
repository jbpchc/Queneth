import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

import email_validator
from pydantic import AfterValidator, BeforeValidator, EmailStr, Field, field_validator

from app.schemas.common import ApiModel

# The demo accounts use the reserved `.test` TLD (spec §13: buyer@queneth.test),
# which email-validator rejects by default. Every other reserved name stays blocked.
if "test" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
    email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("test")


def _normalise_email(value: object) -> object:
    # Postel's Law: accept " Isabela@Example.COM " and store "isabela@example.com".
    return value.strip().lower() if isinstance(value, str) else value


def _normalise_name(value: object) -> object:
    return " ".join(value.split()) if isinstance(value, str) else value


def _check_password(value: str) -> str:
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Use at least one letter and one number.")
    return value


Email = Annotated[EmailStr, BeforeValidator(_normalise_email)]
PersonName = Annotated[str, BeforeValidator(_normalise_name), Field(min_length=2, max_length=120)]
NewPassword = Annotated[str, Field(min_length=8, max_length=128), AfterValidator(_check_password)]


class RegisterRequest(ApiModel):
    name: PersonName = Field(examples=["Isabela Reyes"])
    email: Email = Field(examples=["isabela@queneth.test"])
    password: NewPassword = Field(examples=["Queneth#2026"])


class LoginRequest(ApiModel):
    email: Email
    # No complexity rules on login: old passwords must still work.
    password: str = Field(min_length=1, max_length=128)


class UserOut(ApiModel):
    id: uuid.UUID
    name: str
    email: str
    roles: list[Literal["BUYER", "SELLER", "ADMIN"]]
    avatar_url: str | None
    status: Literal["active", "banned"]
    tier: str
    que_points: int
    email_verified: bool
    created_at: datetime


class MeOut(UserOut):
    """The signed-in user plus their effective permissions, so the frontend can
    hide controls it knows will be refused (UX only; the API still enforces)."""

    permissions: list[str]


class AuthResponse(ApiModel):
    user: MeOut


class MeUpdate(ApiModel):
    name: PersonName | None = None
    #: A ready MediaAsset uploaded with purpose "avatar".
    avatar_asset_id: uuid.UUID | None = None
    clear_avatar: bool = False

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Name can't be empty.")
        return v


class MessageResponse(ApiModel):
    message: str


class TokenRequest(ApiModel):
    token: str = Field(min_length=20, max_length=200)

    @field_validator("token", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        # Postel's Law: tolerate stray whitespace from copy-pasted links.
        return v.strip() if isinstance(v, str) else v


class ForgotPasswordRequest(ApiModel):
    email: Email


class ResetPasswordRequest(TokenRequest):
    password: NewPassword
