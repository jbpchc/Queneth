import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import ApiModel

Pin = Annotated[str, Field(min_length=6, max_length=11, examples=["123456"])]
Category = Literal["payments", "refunds", "topups", "earnings"]


class WalletSummary(ApiModel):
    balance_qc: int
    #: Spendable now. Equals balance for buyers.
    available_qc: int
    #: Seller earnings still held in escrow (filled in by orders, Phase 7).
    pending_qc: int
    has_pin: bool
    locked_until: datetime | None
    topup_presets_qc: list[int]
    topup_today_qc: int
    topup_remaining_today_qc: int
    daily_topup_cap_qc: int


class TopUpRequest(ApiModel):
    amount_qc: int = Field(examples=[5000])


class RedeemRequest(ApiModel):
    code: str = Field(min_length=3, max_length=60, examples=["QUE-DEMO-5000"])


class SetPinRequest(ApiModel):
    pin: Pin


class ChangePinRequest(ApiModel):
    current_pin: Pin
    new_pin: Pin


class WithdrawRequest(ApiModel):
    amount_qc: int = Field(ge=100, le=10_000_000)
    pin: Pin


class LedgerLine(ApiModel):
    """One row of the user's history: their side of a transaction."""

    transaction_id: uuid.UUID
    reference: str
    type: str
    category: str
    memo: str | None
    amount_qc: int
    balance_after_qc: int
    created_at: datetime


class EntryOut(ApiModel):
    wallet: str
    is_you: bool
    amount_qc: int
    balance_after_qc: int | None


class TransactionDetail(ApiModel):
    id: uuid.UUID
    reference: str
    type: str
    category: str
    memo: str | None
    created_at: datetime
    entries: list[EntryOut]
    reversed_by: str | None
    reverses: str | None


class TxResult(ApiModel):
    transaction: LedgerLine
    wallet: WalletSummary


# ─── Admin ─────────────────────────────────────────────────────────────────

Reason = Annotated[str, Field(min_length=5, max_length=300)]


class GrantRequest(ApiModel):
    email: EmailStr
    amount_qc: int = Field(ge=1, le=1_000_000)
    reason: Reason


class CodeCreate(ApiModel):
    amount_qc: int = Field(ge=100, le=1_000_000)
    max_uses: int = Field(default=1, ge=1, le=10_000)
    expires_at: datetime | None = None
    code: str | None = Field(default=None, max_length=40)
    memo: str | None = Field(default=None, max_length=200)

    @field_validator("code")
    @classmethod
    def _blank(cls, v: str | None) -> str | None:
        return v.strip() or None if v else None


class CodeOut(ApiModel):
    id: uuid.UUID
    code: str
    amount_qc: int
    max_uses: int
    used_count: int
    expires_at: datetime | None
    is_active: bool
    memo: str | None
    created_at: datetime


class ReverseRequest(ApiModel):
    reason: Reason


class DriftOut(ApiModel):
    wallet_id: uuid.UUID
    label: str
    cached_qc: int
    computed_qc: int


class ReconcileOut(ApiModel):
    ok: bool
    wallets_checked: int
    transactions_checked: int
    total_balance_qc: int
    drift: list[DriftOut]
    unbalanced_transactions: list[str]


class SystemBalance(ApiModel):
    code: str
    label: str
    balance_qc: int


class AdminTxOut(ApiModel):
    id: uuid.UUID
    reference: str
    type: str
    memo: str | None
    created_at: datetime
    total_qc: int
    entries: list[EntryOut]
    reversed: bool
