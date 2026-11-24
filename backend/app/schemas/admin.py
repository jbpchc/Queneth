import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.schemas.auth import UserOut
from app.schemas.common import ApiModel

Reason = Field(min_length=5, max_length=500, examples=["Approved boutique onboarding"])


class RoleUpdate(ApiModel):
    """The account's one type: BUYER or SELLER (an account is never both).
    ADMIN is seeded, never granted through the API."""

    roles: list[Literal["BUYER", "SELLER"]] = Field(min_length=1)
    reason: str = Reason

    @field_validator("roles")
    @classmethod
    def _one_type(cls, v: list[str]) -> list[str]:
        roles = sorted(set(v))
        if len(roles) != 1:
            raise ValueError("Choose one account type: buyer or seller.")
        return roles


class StatusUpdate(ApiModel):
    status: Literal["active", "banned"]
    reason: str = Reason


class AdminUserOut(UserOut):
    last_login_at: datetime | None


class AuditLogOut(ApiModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    #: "Name <email>" of the actor, or None for system actions.
    actor: str | None = None
    action: str
    target_type: str
    target_id: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str | None
    ip: str | None
    created_at: datetime
