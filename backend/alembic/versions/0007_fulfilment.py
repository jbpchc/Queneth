"""Fulfilment: Que Points ledger, return timestamp, verified-purchase review link.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "points_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("source_key", sa.String(80), nullable=False),
        sa.Column("memo", sa.String(160)),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_points_entries"),
        sa.UniqueConstraint("source_key", name="uq_points_entries_source_key"),
        sa.CheckConstraint("balance_after >= 0", name="ck_points_entries_balance_non_negative"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_points_entries_user_id_users"
        ),
    )
    op.create_index("ix_points_entries_user_id", "points_entries", ["user_id"])

    op.add_column("sub_orders", sa.Column("return_requested_at", TS))
    op.create_index("ix_sub_orders_status_delivered", "sub_orders", ["status", "delivered_at"])

    # Reviews: one per bought line, linked to the order item.
    op.drop_index("ix_reviews_order_item_id", table_name="reviews")
    op.create_unique_constraint("uq_reviews_order_item_id", "reviews", ["order_item_id"])
    op.create_foreign_key(
        "fk_reviews_order_item_id_order_items",
        "reviews",
        "order_items",
        ["order_item_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_reviews_order_item_id_order_items", "reviews", type_="foreignkey")
    op.drop_constraint("uq_reviews_order_item_id", "reviews", type_="unique")
    op.create_index("ix_reviews_order_item_id", "reviews", ["order_item_id"])
    op.drop_index("ix_sub_orders_status_delivered", table_name="sub_orders")
    op.drop_column("sub_orders", "return_requested_at")
    op.drop_index("ix_points_entries_user_id", table_name="points_entries")
    op.drop_table("points_entries")
