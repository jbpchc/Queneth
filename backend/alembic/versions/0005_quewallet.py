"""QueWallet ledger: wallets, transactions, entries, top-up codes, redemptions.

Also seeds the four system wallets so they exist before any money moves.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-13
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    wallets = op.create_table(
        "wallets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_type", sa.String(8), nullable=False),
        sa.Column("user_id", sa.Uuid()),
        sa.Column("system_code", sa.String(24)),
        sa.Column("balance_qc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pin_hash", sa.String(255)),
        sa.Column("pin_failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pin_locked_until", TS),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_wallets"),
        sa.UniqueConstraint("user_id", name="uq_wallets_user_id"),
        sa.UniqueConstraint("system_code", name="uq_wallets_system_code"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_wallets_user_id_users"
        ),
        sa.CheckConstraint(
            "(owner_type = 'user' AND user_id IS NOT NULL AND system_code IS NULL) OR "
            "(owner_type = 'system' AND system_code IS NOT NULL AND user_id IS NULL)",
            name="ck_wallets_owner_valid",
        ),
        sa.CheckConstraint(
            "balance_qc >= 0 OR system_code = 'ISSUANCE'", name="ck_wallets_balance_non_negative"
        ),
    )

    op.create_table(
        "ledger_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(24), nullable=False),
        sa.Column("reference", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("memo", sa.String(300)),
        sa.Column("actor_id", sa.Uuid()),
        sa.Column("reverses_id", sa.Uuid()),
        sa.Column("meta", pg.JSONB(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_transactions"),
        sa.UniqueConstraint("reference", name="uq_ledger_transactions_reference"),
        sa.UniqueConstraint("idempotency_key", name="uq_ledger_transactions_idempotency_key"),
        sa.UniqueConstraint("reverses_id", name="uq_ledger_transactions_reverses_id"),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_ledger_transactions_actor_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["reverses_id"],
            ["ledger_transactions.id"],
            ondelete="RESTRICT",
            name="fk_ledger_transactions_reverses_id_ledger_transactions",
        ),
    )
    op.create_index("ix_ledger_transactions_type", "ledger_transactions", ["type"])
    op.create_index("ix_ledger_transactions_actor_id", "ledger_transactions", ["actor_id"])
    op.create_index("ix_ledger_transactions_created_at", "ledger_transactions", ["created_at"])

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=False),
        sa.Column("amount_qc", sa.Integer(), nullable=False),
        sa.Column("balance_after_qc", sa.Integer(), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_entries"),
        sa.CheckConstraint("amount_qc <> 0", name="ck_ledger_entries_amount_non_zero"),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["ledger_transactions.id"],
            ondelete="RESTRICT",
            name="fk_ledger_entries_transaction_id_ledger_transactions",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            ondelete="RESTRICT",
            name="fk_ledger_entries_wallet_id_wallets",
        ),
    )
    op.create_index("ix_ledger_entries_transaction_id", "ledger_entries", ["transaction_id"])
    op.create_index("ix_ledger_entries_wallet_id", "ledger_entries", ["wallet_id"])
    op.create_index(
        "ix_ledger_entries_wallet_created", "ledger_entries", ["wallet_id", "created_at"]
    )
    # Ledger entries are immutable: refuse UPDATE and DELETE at the database level.
    op.execute(
        """
        CREATE FUNCTION ledger_entries_immutable() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'ledger_entries are append-only (use a REVERSAL transaction)';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER ledger_entries_no_update_delete
          BEFORE UPDATE OR DELETE ON ledger_entries
          FOR EACH ROW EXECUTE FUNCTION ledger_entries_immutable();
        """
    )

    op.create_table(
        "topup_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("amount_qc", sa.Integer(), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", TS),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("memo", sa.String(200)),
        sa.Column("created_by", sa.Uuid()),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_topup_codes"),
        sa.UniqueConstraint("code", name="uq_topup_codes_code"),
        sa.CheckConstraint("amount_qc > 0", name="ck_topup_codes_amount_positive"),
        sa.CheckConstraint("used_count <= max_uses", name="ck_topup_codes_uses_within_limit"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_topup_codes_created_by_users",
        ),
    )

    op.create_table(
        "code_redemptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_code_redemptions"),
        sa.UniqueConstraint("code_id", "user_id", name="uq_code_redemptions_code_user"),
        sa.ForeignKeyConstraint(
            ["code_id"],
            ["topup_codes.id"],
            ondelete="RESTRICT",
            name="fk_code_redemptions_code_id_topup_codes",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_code_redemptions_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["ledger_transactions.id"],
            ondelete="RESTRICT",
            name="fk_code_redemptions_transaction_id_ledger_transactions",
        ),
    )
    op.create_index("ix_code_redemptions_code_id", "code_redemptions", ["code_id"])
    op.create_index("ix_code_redemptions_user_id", "code_redemptions", ["user_id"])

    op.bulk_insert(
        wallets,
        [
            {
                "id": uuid.uuid4(),
                "owner_type": "system",
                "system_code": code,
                "balance_qc": 0,
                "pin_failed_attempts": 0,
            }
            for code in ("ISSUANCE", "ESCROW", "PLATFORM_REVENUE", "OUT_SIMULATED")
        ],
    )


def downgrade() -> None:
    op.drop_table("code_redemptions")
    op.drop_table("topup_codes")
    op.execute("DROP TRIGGER IF EXISTS ledger_entries_no_update_delete ON ledger_entries")
    op.execute("DROP FUNCTION IF EXISTS ledger_entries_immutable()")
    op.drop_table("ledger_entries")
    op.drop_table("ledger_transactions")
    op.drop_table("wallets")
