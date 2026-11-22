"""Moderation: shopper reports on products and reviews.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "content_flags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(24), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("status", sa.String(12), nullable=False, server_default="open"),
        sa.Column("resolution", sa.String(24)),
        sa.Column("resolved_by", sa.Uuid()),
        sa.Column("resolved_at", TS),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_content_flags"),
        sa.CheckConstraint(
            "target_type IN ('product', 'review')", name="ck_content_flags_target_type_valid"
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_content_flags_reporter_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_content_flags_resolved_by_users",
        ),
    )
    op.create_index("ix_content_flags_target_id", "content_flags", ["target_id"])
    op.create_index("ix_content_flags_reporter_id", "content_flags", ["reporter_id"])
    op.create_index("ix_content_flags_status", "content_flags", ["status"])
    op.create_index(
        "ix_content_flags_target", "content_flags", ["target_type", "target_id", "status"]
    )
    # Only one open report per shopper per target (resolved ones can repeat).
    op.create_index(
        "uq_content_flags_open_per_reporter",
        "content_flags",
        ["reporter_id", "target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_table("content_flags")
