import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.permissions import Role
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import EmailType, JSONType, StringArray, TZDateTime

if TYPE_CHECKING:
    from app.models.catalog import SellerProfile


class UserStatus(StrEnum):
    ACTIVE = "active"
    BANNED = "banned"


class Tier(StrEnum):
    INGENUE = "INGENUE"
    AFICIONADO = "AFICIONADO"
    CONNOISSEUR = "CONNOISSEUR"
    MAISON = "MAISON"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One account per person. A seller is a buyer with the SELLER role added
    (roles are stored as an array), so they keep every buyer ability."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'banned')", name="status_valid"),
        CheckConstraint("que_points >= 0", name="points_non_negative"),
        Index("ix_users_roles", "roles", postgresql_using="gin"),
    )

    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(EmailType, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    roles: Mapped[list[str]] = mapped_column(StringArray, default=lambda: [Role.BUYER.value])
    avatar_url: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[str] = mapped_column(String(16), default=UserStatus.ACTIVE.value)
    tier: Mapped[str] = mapped_column(String(24), default=Tier.INGENUE.value)
    que_points: Mapped[int] = mapped_column(Integer, default=0)
    style_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None)
    email_verified_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    last_login_at: Mapped[datetime | None] = mapped_column(TZDateTime())

    seller_profile: Mapped["SellerProfile | None"] = relationship(
        back_populates="user",
        lazy="selectin",
        uselist=False,
        foreign_keys="SellerProfile.user_id",
    )

    @property
    def seller_id(self) -> uuid.UUID | None:
        """Ownership key for seller-owned resources (products, drops, sub-orders).
        Only an *approved* boutique owns anything; pending/suspended ones don't."""
        profile = self.seller_profile
        return profile.id if profile is not None and profile.status == "approved" else None

    def has_role(self, role: Role | str) -> bool:
        return str(role) in (self.roles or [])

    @property
    def is_banned(self) -> bool:
        return self.status == UserStatus.BANNED.value


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Server-side record of every refresh token (the id is the JWT `jti`).

    Tokens rotate on each refresh. All tokens issued from one login share a
    `family_id`; presenting an already-rotated token revokes the whole family
    (refresh-token reuse detection).
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    user_agent: Mapped[str | None] = mapped_column(String(300))
    ip: Mapped[str | None] = mapped_column(String(64))


class EmailToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Single-use token for email verification or password reset. Only a
    SHA-256 hash is stored; the raw token exists only in the emailed link."""

    __tablename__ = "email_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(24))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime())
    used_at: Mapped[datetime | None] = mapped_column(TZDateTime())


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Append-only record of admin actions and role changes (spec §7, layer 5)."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_target", "target_type", "target_id"),)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(48))
    target_id: Mapped[str] = mapped_column(String(64))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    reason: Mapped[str | None] = mapped_column(String(500))
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime(), default=lambda: datetime.now().astimezone(), index=True
    )
