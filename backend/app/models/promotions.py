"""Platform promotions (spec: deals, discounts and promos).

A `Promotion` is a campaign run by Queneth admins ("End of the Year Sale").
Sellers enroll their own pieces with a discount (`PromotionEntry`). While the
campaign is live the piece's variant prices drop by that percentage and the
original price is kept as the compare-at ("was") price; when it ends — or the
seller withdraws — prices are restored from the snapshot taken at the start.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, TZDateTime


class Promotion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "promotions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="window_valid"),
        CheckConstraint(
            "min_discount_percent BETWEEN 1 AND 90 AND max_discount_percent BETWEEN 1 AND 90 "
            "AND min_discount_percent <= max_discount_percent",
            name="discount_range_valid",
        ),
        Index("ix_promotions_window", "starts_at", "ends_at"),
    )

    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    #: Short label on cards and banners, e.g. "Year-End Sale".
    badge: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    hero_url: Mapped[str | None] = mapped_column(String(500))
    starts_at: Mapped[datetime] = mapped_column(TZDateTime())
    ends_at: Mapped[datetime] = mapped_column(TZDateTime())
    min_discount_percent: Mapped[int] = mapped_column(Integer, default=5)
    max_discount_percent: Mapped[int] = mapped_column(Integer, default=70)
    #: Admins can call a campaign off; live prices are then restored.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    entries: Mapped[list["PromotionEntry"]] = relationship(
        back_populates="promotion", lazy="selectin"
    )


class PromotionEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "promotion_entries"
    __table_args__ = (
        UniqueConstraint(
            "promotion_id", "product_id", name="uq_promotion_entries_promotion_product"
        ),
        CheckConstraint("discount_percent BETWEEN 1 AND 90", name="discount_valid"),
        CheckConstraint(
            "status IN ('scheduled', 'live', 'ended', 'withdrawn')", name="status_valid"
        ),
        Index("ix_promotion_entries_status", "status"),
    )

    promotion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("promotions.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seller_profiles.id", ondelete="CASCADE"), index=True
    )
    discount_percent: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="scheduled")
    #: {variant_id: [price_qc, compare_at_qc|None]} captured when the sale starts.
    original_prices: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    applied_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    ended_at: Mapped[datetime | None] = mapped_column(TZDateTime())

    promotion: Mapped[Promotion] = relationship(back_populates="entries", lazy="joined")
