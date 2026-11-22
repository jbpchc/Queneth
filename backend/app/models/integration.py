import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, TZDateTime


class GeoCache(Base):
    """PSGC responses cached for 30 days (geographic data rarely changes)."""

    __tablename__ = "geo_cache"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    payload: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)
    fetched_at: Mapped[datetime] = mapped_column(TZDateTime())


class MediaAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An uploaded image. `provider` says where the bytes live: Cloudinary, or
    local disk when Cloudinary is in mock mode, unconfigured or unreachable."""

    __tablename__ = "media_assets"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(24))
    provider: Mapped[str] = mapped_column(String(16))
    public_id: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    content_type: Mapped[str] = mapped_column(String(32))
    bytes: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    format: Mapped[str | None] = mapped_column(String(16))
    url: Mapped[str | None] = mapped_column(String(500))


class EmailLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Every transactional email, queued before sending and retried on failure.

    Status: queued → sent | mocked | failed. The body is kept for retries but is
    never returned by the API except as an admin preview of *mocked* emails."""

    __tablename__ = "email_logs"
    __table_args__ = (Index("ix_email_logs_status_next", "status", "next_attempt_at"),)

    to_email: Mapped[str] = mapped_column(String(320))
    to_name: Mapped[str | None] = mapped_column(String(120))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    template: Mapped[str] = mapped_column(String(48), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    html: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    last_error: Mapped[str | None] = mapped_column(String(300))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    sent_at: Mapped[datetime | None] = mapped_column(TZDateTime())


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """In-app inbox. Every email to a user is mirrored here, so the message
    still reaches them if email delivery fails (spec §3 fallbacks)."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "read_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    read_at: Mapped[datetime | None] = mapped_column(TZDateTime())


class ContentFlag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A shopper's report on a product or review (moderation queue, spec §10).

    One open report per reporter per target; resolving records who decided what.
    """

    __tablename__ = "content_flags"
    __table_args__ = (
        Index("ix_content_flags_target", "target_type", "target_id", "status"),
        # One open report per shopper per target; resolved ones may repeat.
        Index(
            "uq_content_flags_open_per_reporter",
            "reporter_id",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
            sqlite_where=text("status = 'open'"),
        ),
    )

    target_type: Mapped[str] = mapped_column(String(16))  # product | review
    target_id: Mapped[uuid.UUID] = mapped_column(index=True)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(24))
    note: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)
    resolution: Mapped[str | None] = mapped_column(String(24))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime())
