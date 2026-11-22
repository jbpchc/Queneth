"""External integrations: geo cache, media assets, email log, email tokens,
notifications.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _user_fk(table: str, column: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["users.id"], ondelete=ondelete, name=f"fk_{table}_{column}_users"
    )


def upgrade() -> None:
    op.create_table(
        "geo_cache",
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_geo_cache"),
    )

    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("public_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("bytes", sa.Integer()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("format", sa.String(16)),
        sa.Column("url", sa.String(500)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_media_assets"),
        sa.UniqueConstraint("public_id", name="uq_media_assets_public_id"),
        _user_fk("media_assets", "owner_id", "CASCADE"),
    )
    op.create_index("ix_media_assets_owner_id", "media_assets", ["owner_id"])

    op.create_table(
        "email_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("to_email", sa.String(320), nullable=False),
        sa.Column("to_name", sa.String(120)),
        sa.Column("user_id", sa.Uuid()),
        sa.Column("template", sa.String(48), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(300)),
        sa.Column("provider_message_id", sa.String(200)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_email_logs"),
        _user_fk("email_logs", "user_id", "SET NULL"),
    )
    op.create_index("ix_email_logs_user_id", "email_logs", ["user_id"])
    op.create_index("ix_email_logs_template", "email_logs", ["template"])
    op.create_index("ix_email_logs_status_next", "email_logs", ["status", "next_attempt_at"])

    op.create_table(
        "email_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_email_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_email_tokens_token_hash"),
        _user_fk("email_tokens", "user_id", "CASCADE"),
    )
    op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(48), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        _user_fk("notifications", "user_id", "CASCADE"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "read_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("email_tokens")
    op.drop_table("email_logs")
    op.drop_table("media_assets")
    op.drop_table("geo_cache")
