"""Commerce: addresses, vouchers, cart vouchers, wishlist boards, orders,
sub-orders, order items, status events, voucher redemptions.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), nullable=False)


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    ]


def _fk(table: str, col: str, ref: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([col], [f"{ref}.id"], ondelete=ondelete, name=f"fk_{table}_{col}_{ref}")


def upgrade() -> None:
    op.create_table(
        "addresses",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(40), nullable=False),
        sa.Column("recipient", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("line1", sa.String(200), nullable=False),
        sa.Column("barangay_code", sa.String(9), nullable=False),
        sa.Column("barangay", sa.String(120), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("province", sa.String(120)),
        sa.Column("region", sa.String(120), nullable=False),
        sa.Column("zip", sa.String(4), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_addresses"),
        _fk("addresses", "user_id", "users", "CASCADE"),
    )
    op.create_index("ix_addresses_user_id", "addresses", ["user_id"])

    op.create_table(
        "vouchers",
        _id(),
        sa.Column("seller_id", sa.Uuid()),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("type", sa.String(8), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("min_spend_qc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", TS),
        sa.Column("ends_at", TS),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("description", sa.String(160)),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_vouchers"),
        sa.UniqueConstraint("code", name="uq_vouchers_code"),
        sa.CheckConstraint("type IN ('percent', 'fixed')", name="ck_vouchers_type_valid"),
        sa.CheckConstraint(
            "(type = 'percent' AND value BETWEEN 1 AND 90) OR (type = 'fixed' AND value > 0)",
            name="ck_vouchers_value_valid",
        ),
        sa.CheckConstraint("used_count <= max_uses", name="ck_vouchers_uses_within_limit"),
        _fk("vouchers", "seller_id", "seller_profiles", "CASCADE"),
    )
    op.create_index("ix_vouchers_seller_id", "vouchers", ["seller_id"])

    op.create_table(
        "cart_vouchers",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("voucher_id", sa.Uuid(), nullable=False),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_cart_vouchers"),
        sa.UniqueConstraint("user_id", "voucher_id", name="uq_cart_vouchers_user_voucher"),
        _fk("cart_vouchers", "user_id", "users", "CASCADE"),
        _fk("cart_vouchers", "voucher_id", "vouchers", "CASCADE"),
    )
    op.create_index("ix_cart_vouchers_user_id", "cart_vouchers", ["user_id"])
    op.create_index("ix_cart_vouchers_voucher_id", "cart_vouchers", ["voucher_id"])

    op.create_table(
        "wishlist_boards",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(48), nullable=False),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_wishlist_boards"),
        sa.UniqueConstraint("user_id", "name", name="uq_wishlist_boards_user_name"),
        _fk("wishlist_boards", "user_id", "users", "CASCADE"),
    )
    op.create_index("ix_wishlist_boards_user_id", "wishlist_boards", ["user_id"])
    op.create_foreign_key(
        "fk_wishlist_items_board_id_wishlist_boards",
        "wishlist_items",
        "wishlist_boards",
        ["board_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "orders",
        _id(),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(16), nullable=False),
        sa.Column("subtotal_qc", sa.Integer(), nullable=False),
        sa.Column("discount_qc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_qc", sa.Integer(), nullable=False),
        sa.Column("shipping_address", pg.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("points_pending", sa.Integer(), nullable=False, server_default="0"),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_orders"),
        sa.UniqueConstraint("number", name="uq_orders_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_orders_idempotency_key"),
        sa.CheckConstraint("total_qc >= 0", name="ck_orders_total_non_negative"),
        _fk("orders", "buyer_id", "users", "RESTRICT"),
    )
    op.create_index("ix_orders_buyer_id", "orders", ["buyer_id"])
    op.create_index("ix_orders_buyer_created", "orders", ["buyer_id", "created_at"])

    op.create_table(
        "sub_orders",
        _id(),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("items_total_qc", sa.Integer(), nullable=False),
        sa.Column("discount_qc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subtotal_qc", sa.Integer(), nullable=False),
        sa.Column("commission_qc", sa.Integer(), nullable=False),
        sa.Column("voucher_code", sa.String(32)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("tracking_no", sa.String(40)),
        sa.Column("payment_tx_id", sa.Uuid()),
        sa.Column("shipped_at", TS),
        sa.Column("delivered_at", TS),
        sa.Column("escrow_released_at", TS),
        sa.Column("return_reason", sa.Text()),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_sub_orders"),
        sa.UniqueConstraint("number", name="uq_sub_orders_number"),
        _fk("sub_orders", "order_id", "orders", "CASCADE"),
        _fk("sub_orders", "seller_id", "seller_profiles", "RESTRICT"),
        _fk("sub_orders", "payment_tx_id", "ledger_transactions", "RESTRICT"),
    )
    op.create_index("ix_sub_orders_order_id", "sub_orders", ["order_id"])
    op.create_index("ix_sub_orders_seller_id", "sub_orders", ["seller_id"])
    op.create_index("ix_sub_orders_seller_status", "sub_orders", ["seller_id", "status"])

    op.create_table(
        "order_items",
        _id(),
        sa.Column("sub_order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("title_snapshot", sa.String(160), nullable=False),
        sa.Column("brand_snapshot", sa.String(80), nullable=False),
        sa.Column("options_snapshot", pg.JSONB(), nullable=False),
        sa.Column("image_snapshot", sa.String(500)),
        sa.Column("product_slug", sa.String(160), nullable=False),
        sa.Column("unit_price_qc", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("line_total_qc", sa.Integer(), nullable=False),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_order_items"),
        sa.CheckConstraint("qty BETWEEN 1 AND 10", name="ck_order_items_qty_range"),
        _fk("order_items", "sub_order_id", "sub_orders", "CASCADE"),
        _fk("order_items", "product_id", "products", "RESTRICT"),
        _fk("order_items", "variant_id", "variants", "RESTRICT"),
    )
    for col in ("sub_order_id", "product_id", "variant_id"):
        op.create_index(f"ix_order_items_{col}", "order_items", [col])

    op.create_table(
        "order_status_events",
        _id(),
        sa.Column("sub_order_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("note", sa.String(300)),
        sa.Column("created_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_order_status_events"),
        _fk("order_status_events", "sub_order_id", "sub_orders", "CASCADE"),
        _fk("order_status_events", "actor_id", "users", "SET NULL"),
    )
    op.create_index("ix_order_status_events_sub_order_id", "order_status_events", ["sub_order_id"])

    op.create_table(
        "voucher_redemptions",
        _id(),
        sa.Column("voucher_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sub_order_id", sa.Uuid(), nullable=False),
        sa.Column("discount_qc", sa.Integer(), nullable=False),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_voucher_redemptions"),
        sa.UniqueConstraint("voucher_id", "user_id", name="uq_voucher_redemptions_voucher_user"),
        _fk("voucher_redemptions", "voucher_id", "vouchers", "RESTRICT"),
        _fk("voucher_redemptions", "user_id", "users", "CASCADE"),
        _fk("voucher_redemptions", "sub_order_id", "sub_orders", "RESTRICT"),
    )
    for col in ("voucher_id", "user_id", "sub_order_id"):
        op.create_index(f"ix_voucher_redemptions_{col}", "voucher_redemptions", [col])


def downgrade() -> None:
    for t in ("voucher_redemptions", "order_status_events", "order_items", "sub_orders", "orders"):
        op.drop_table(t)
    op.drop_constraint("fk_wishlist_items_board_id_wishlist_boards", "wishlist_items", type_="foreignkey")
    for t in ("wishlist_boards", "cart_vouchers", "vouchers", "addresses"):
        op.drop_table(t)
