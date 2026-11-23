"""Promotions: platform campaigns and the seller pieces enrolled in them.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "promotions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("badge", sa.String(32), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("hero_url", sa.String(500)),
        sa.Column("starts_at", TS, nullable=False),
        sa.Column("ends_at", TS, nullable=False),
        sa.Column("min_discount_percent", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("max_discount_percent", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid()),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_promotions"),
        sa.UniqueConstraint("slug", name="uq_promotions_slug"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_promotions_window_valid"),
        sa.CheckConstraint(
            "min_discount_percent BETWEEN 1 AND 90 AND max_discount_percent BETWEEN 1 AND 90 "
            "AND min_discount_percent <= max_discount_percent",
            name="ck_promotions_discount_range_valid",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL", name="fk_promotions_created_by_users"
        ),
    )
    op.create_index("ix_promotions_window", "promotions", ["starts_at", "ends_at"])

    op.create_table(
        "promotion_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("promotion_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="scheduled"),
        sa.Column("original_prices", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("applied_at", TS),
        sa.Column("ended_at", TS),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_promotion_entries"),
        sa.UniqueConstraint(
            "promotion_id", "product_id", name="uq_promotion_entries_promotion_product"
        ),
        sa.CheckConstraint(
            "discount_percent BETWEEN 1 AND 90", name="ck_promotion_entries_discount_valid"
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'live', 'ended', 'withdrawn')",
            name="ck_promotion_entries_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["promotion_id"],
            ["promotions.id"],
            ondelete="CASCADE",
            name="fk_promotion_entries_promotion_id_promotions",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
            name="fk_promotion_entries_product_id_products",
        ),
        sa.ForeignKeyConstraint(
            ["seller_id"],
            ["seller_profiles.id"],
            ondelete="CASCADE",
            name="fk_promotion_entries_seller_id_seller_profiles",
        ),
    )
    for col in ("promotion_id", "product_id", "seller_id"):
        op.create_index(f"ix_promotion_entries_{col}", "promotion_entries", [col])
    op.create_index("ix_promotion_entries_status", "promotion_entries", ["status"])


def downgrade() -> None:
    op.drop_table("promotion_entries")
    op.drop_table("promotions")
