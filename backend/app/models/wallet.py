"""QueWallet: a closed-loop, double-entry credit ledger (spec §8).

- One Wallet per user, plus system wallets (ISSUANCE, ESCROW, PLATFORM_REVENUE,
  OUT_SIMULATED). ISSUANCE is the source of every minted credit and is the only
  wallet allowed below zero, so the sum of all balances is always 0.
- Every movement is one LedgerTransaction with ≥ 2 LedgerEntry rows that sum
  to zero. Entries are never updated or deleted; corrections are new
  REVERSAL transactions.
- Amounts are integers (whole QC). Never floats.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, TZDateTime


class SystemWallet(StrEnum):
    ISSUANCE = "ISSUANCE"
    ESCROW = "ESCROW"
    PLATFORM_REVENUE = "PLATFORM_REVENUE"
    OUT_SIMULATED = "OUT_SIMULATED"


class TxType(StrEnum):
    GRANT = "GRANT"
    TOPUP = "TOPUP"
    VOUCHER_REDEEM = "VOUCHER_REDEEM"
    PAYMENT = "PAYMENT"
    ESCROW_RELEASE = "ESCROW_RELEASE"
    COMMISSION = "COMMISSION"
    REFUND = "REFUND"
    WITHDRAWAL = "WITHDRAWAL"
    REVERSAL = "REVERSAL"


class Wallet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint(
            "(owner_type = 'user' AND user_id IS NOT NULL AND system_code IS NULL) OR "
            "(owner_type = 'system' AND system_code IS NOT NULL AND user_id IS NULL)",
            name="owner_valid",
        ),
        # Database-level guarantee: no wallet but ISSUANCE can go negative.
        CheckConstraint("balance_qc >= 0 OR system_code = 'ISSUANCE'", name="balance_non_negative"),
    )

    owner_type: Mapped[str] = mapped_column(String(8))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True
    )
    system_code: Mapped[str | None] = mapped_column(String(24), unique=True)
    #: Cached balance, updated in the same DB transaction as its entries.
    balance_qc: Mapped[int] = mapped_column(Integer, default=0)
    pin_hash: Mapped[str | None] = mapped_column(String(255))
    pin_failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    pin_locked_until: Mapped[datetime | None] = mapped_column(TZDateTime())


class LedgerTransaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ledger_transactions"

    type: Mapped[str] = mapped_column(String(24), index=True)
    #: Human-readable id, shown chunked in the UI: QW-2026-1112-482107.
    reference: Mapped[str] = mapped_column(String(24), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    memo: Mapped[str | None] = mapped_column(String(300))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    #: Set on REVERSAL transactions; unique, so a transaction is reversed at most once.
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), unique=True
    )
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), index=True)

    entries: Mapped[list["LedgerEntry"]] = relationship(
        lazy="selectin", order_by="LedgerEntry.amount_qc", back_populates="transaction"
    )


class LedgerEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount_qc <> 0", name="amount_non_zero"),
        Index("ix_ledger_entries_wallet_created", "wallet_id", "created_at"),
    )

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), index=True
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wallets.id", ondelete="RESTRICT"), index=True
    )
    #: Signed: credit > 0, debit < 0.
    amount_qc: Mapped[int] = mapped_column(Integer)
    balance_after_qc: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TZDateTime())

    transaction: Mapped[LedgerTransaction] = relationship(back_populates="entries")
    wallet: Mapped[Wallet] = relationship(lazy="joined")


class TopUpCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Admin-issued voucher code (e.g. QUE-DEMO-5000), single- or limited-use."""

    __tablename__ = "topup_codes"
    __table_args__ = (
        CheckConstraint("amount_qc > 0", name="amount_positive"),
        CheckConstraint("used_count <= max_uses", name="uses_within_limit"),
    )

    code: Mapped[str] = mapped_column(String(40), unique=True)
    amount_qc: Mapped[int] = mapped_column(Integer)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    is_active: Mapped[bool] = mapped_column(default=True)
    memo: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class CodeRedemption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "code_redemptions"
    __table_args__ = (UniqueConstraint("code_id", "user_id", name="uq_code_redemptions_code_user"),)

    code_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topup_codes.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT")
    )
