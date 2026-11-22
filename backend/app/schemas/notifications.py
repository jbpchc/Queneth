import uuid
from datetime import datetime
from typing import Any, Literal

from app.schemas.common import ApiModel


class NotificationOut(ApiModel):
    id: uuid.UUID
    type: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class UnreadCount(ApiModel):
    unread: int


class IntegrationStatusOut(ApiModel):
    name: Literal["psgc", "cloudinary", "brevo"]
    label: str
    purpose: str
    mode: Literal["live", "mock"]
    configured: bool
    #: "ok" = recent success, "degraded" = latest call failed (fallback active),
    #: "mock" = mock mode, "unconfigured" = live mode without credentials, "idle" = no calls yet.
    health: Literal["ok", "degraded", "mock", "unconfigured", "idle"]
    calls: int
    failures: int
    fallbacks: int
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None
    last_latency_ms: int | None
    last_fallback_at: datetime | None
    fallback: str
    details: dict[str, Any]


class EmailLogOut(ApiModel):
    id: uuid.UUID
    to_email: str
    template: str
    subject: str
    status: Literal["queued", "sent", "mocked", "failed"]
    attempts: int
    last_error: str | None
    provider_message_id: str | None
    next_attempt_at: datetime | None
    sent_at: datetime | None
    created_at: datetime


class EmailPreview(ApiModel):
    subject: str
    html: str
    text: str
