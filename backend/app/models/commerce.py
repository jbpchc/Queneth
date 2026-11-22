"""Commerce: address book, seller vouchers, wishlist boards and orders.

An Order is what the buyer paid for in one checkout. It is split into one
SubOrder per boutique (spec §11): each is paid into escrow separately,
fulfilled separately, and released to its seller separately.
"""

import uuid
from datetime import datetime
from enum import StrEnum
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


class Address(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A saved shipping address. Place names are resolved server-side from the
    PSGC barangay code, never trusted from the client."""

    __tablename__ = "addresses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(40))
    recipient: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))  # E.164, e.g. +639171234567
    line1: Mapped[str] = mapped_column(String(200))
    barangay_code: Mapped[str] = mapped_column(String(9))
    barangay: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(120))
    province: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(120))
    zip: Mapped[str] = mapped_column(String(4))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    def snapshot(self) -> dict[str, Any]:
        """Frozen copy stored on the order, so later edits never rewrite history."""
        return {
            "label": self.label,
            "recipient": self.recipient,
            "phone": self.phone,
            "line1": self.line1,
            "barangay_code": self.barangay_code,
            "barangay": self.barangay,
            "city": self.city,
            "province": self.province,
            "region": self.region,
            "zip": self.zip,
        }


class Voucher(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Seller-funded voucher: percent or fixed QC off that boutique's items."""

    __tablename__ = "vouchers"
    __table_args__ = (
        CheckConstraint("type IN ('percent', 'fixed')", name="type_valid"),
        CheckConstraint(
            "(type = 'percent' AND value BETWEEN 1 AND 90) OR (type = 'fixed' AND value > 0)",
            name="value_valid",
        ),
        CheckConstraint("used_count <= max_uses", name="uses_within_limit"),
        UniqueConstraint("code", name="uq_vouchers_code"),
    )

    seller_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seller_profiles.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(32))
    type: Mapped[str] = mapped_column(String(8))
    value: Mapped[int] = mapped_column(Integer)
    min_spend_qc: Mapped[int] = mapped_column(Integer, default=0)
    max_uses: Mapped[int] = mapped_column(Integer, default=100)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    #: Each buyer can use a voucher once.
    starts_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    ends_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(String(160))


class CartVoucher(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A voucher applied to the bag (at most one per boutique)."""

    __tablename__ = "cart_vouchers"
    __table_args__ = (
        UniqueConstraint("user_id", "voucher_id", name="uq_cart_vouchers_user_voucher"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), index=True
    )

    voucher: Mapped[Voucher] = relationship(lazy="joined")


class VoucherRedemption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "voucher_redemptions"
    __table_args__ = (
        UniqueConstraint("voucher_id", "user_id", name="uq_voucher_redemptions_voucher_user"),
    )

    voucher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vouchers.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    sub_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sub_orders.id", ondelete="RESTRICT"), index=True
    )
    discount_qc: Mapped[int] = mapped_column(Integer)


class WishlistBoard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Named wishlist board ("Wedding season", "Signature scents")."""

    __tablename__ = "wishlist_boards"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_wishlist_boards_user_name"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(48))


class OrderStatus(StrEnum):
    PAID = "PAID"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RETURN_REQUESTED = "RETURN_REQUESTED"
    REFUNDED = "REFUNDED"


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_qc >= 0", name="total_non_negative"),
        Index("ix_orders_buyer_created", "buyer_id", "created_at"),
    )

    buyer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    #: QN-2026-4821 (sub-orders append -01, -02 …), shown chunked in the UI.
    number: Mapped[str] = mapped_column(String(16), unique=True)
    subtotal_qc: Mapped[int] = mapped_column(Integer)
    discount_qc: Mapped[int] = mapped_column(Integer, default=0)
    total_qc: Mapped[int] = mapped_column(Integer)
    shipping_address: Mapped[dict[str, Any]] = mapped_column(JSONType)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    #: Rollup of the sub-orders' statuses (see order_service.rollup).
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.PAID.value)
    points_pending: Mapped[int] = mapped_column(Integer, default=0)

    sub_orders: Mapped[list["SubOrder"]] = relationship(
        back_populates="order", lazy="selectin", order_by="SubOrder.number"
    )


class SubOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sub_orders"
    __table_args__ = (
        Index("ix_sub_orders_seller_status", "seller_id", "status"),
        Index("ix_sub_orders_status_delivered", "status", "delivered_at"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seller_profiles.id", ondelete="RESTRICT"), index=True
    )
    number: Mapped[str] = mapped_column(String(20), unique=True)
    items_total_qc: Mapped[int] = mapped_column(Integer)
    discount_qc: Mapped[int] = mapped_column(Integer, default=0)
    #: What the buyer paid into escrow for this boutique (items − discount).
    subtotal_qc: Mapped[int] = mapped_column(Integer)
    #: 5 % platform commission, deducted when escrow is released.
    commission_qc: Mapped[int] = mapped_column(Integer)
    voucher_code: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.PAID.value)
    tracking_no: Mapped[str | None] = mapped_column(String(40))
    payment_tx_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT")
    )
    shipped_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    delivered_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    escrow_released_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    return_requested_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    return_reason: Mapped[str | None] = mapped_column(Text)

    order: Mapped[Order] = relationship(back_populates="sub_orders")
    items: Mapped[list["OrderItem"]] = relationship(
        lazy="selectin", order_by="OrderItem.title_snapshot"
    )
    events: Mapped[list["OrderStatusEvent"]] = relationship(
        lazy="selectin", order_by="OrderStatusEvent.created_at"
    )


class OrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("qty BETWEEN 1 AND 10", name="qty_range"),)

    sub_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sub_orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("variants.id", ondelete="RESTRICT"), index=True
    )
    # Snapshots: the order shows what was bought, even if the listing changes.
    title_snapshot: Mapped[str] = mapped_column(String(160))
    brand_snapshot: Mapped[str] = mapped_column(String(80))
    options_snapshot: Mapped[dict[str, str]] = mapped_column(JSONType)
    image_snapshot: Mapped[str | None] = mapped_column(String(500))
    product_slug: Mapped[str] = mapped_column(String(160))
    unit_price_qc: Mapped[int] = mapped_column(Integer)
    qty: Mapped[int] = mapped_column(Integer)
    line_total_qc: Mapped[int] = mapped_column(Integer)


class OrderStatusEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "order_status_events"

    sub_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sub_orders.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(TZDateTime())


class PointsEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Que Points ledger (append-only). `User.que_points` caches the sum.

    1 point per 100 QC on completed sub-orders (spec §6). `source_key` is unique,
    so the same sub-order can never award points twice.
    """

    __tablename__ = "points_entries"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(32))  # order_completed, redeemed (Phase 10)
    source_key: Mapped[str] = mapped_column(String(80), unique=True)
    memo: Mapped[str | None] = mapped_column(String(160))
