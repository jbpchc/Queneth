"""Seller Studio: storefront settings, rejection reason, first-sale banner,
bag-add funnel counter, drop go-live notification marker.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("seller_profiles", sa.Column("rejection_reason", sa.Text()))
    op.add_column(
        "seller_profiles",
        sa.Column("featured_product_ids", pg.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "seller_profiles", sa.Column("lookbook", pg.JSONB(), nullable=False, server_default="[]")
    )
    op.add_column("seller_profiles", sa.Column("first_sale_seen_at", TS))
    op.add_column(
        "products",
        sa.Column("bag_add_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("drops", sa.Column("notified_at", TS))
    op.create_index("ix_drops_pending_notify", "drops", ["notified_at", "starts_at"])


def downgrade() -> None:
    op.drop_index("ix_drops_pending_notify", table_name="drops")
    op.drop_column("drops", "notified_at")
    op.drop_column("products", "bag_add_count")
    for col in ("first_sale_seen_at", "lookbook", "featured_product_ids", "rejection_reason"):
        op.drop_column("seller_profiles", col)
