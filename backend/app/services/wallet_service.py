"""QueWallet: the only payment method (spec §8). Closed loop, simulated credits.

Invariants (each enforced in code, most also by the database):
1. Every LedgerTransaction's entries sum to zero (double entry).
2. Entries are append-only; corrections are REVERSAL transactions.
3. Wallet.balance_qc equals the sum of its entries (see reconcile()).
4. No wallet but ISSUANCE goes negative (CHECK constraint + checks here).
5. Each movement carries a unique idempotency key: retrying a request (a
   double-tapped Pay button) returns the original transaction, never a second one.
6. Wallet rows are locked (SELECT … FOR UPDATE) in id order before any balance
   changes, so concurrent payments can't overdraw and can't deadlock.

`post()` and the escrow primitives do not commit: callers wrap them in
`atomic(session)`, so an order and its payment (Phase 6) land in one transaction.
"""

import csv
import io
import secrets
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Conflict, NotFound, ValidationFailed
from app.core.permissions import Permission, assert_can
from app.core.security import as_aware, hash_password, utcnow, verify_password
from app.db.atomic import atomic
from app.models.integration import Notification
from app.models.user import User
from app.models.wallet import (
    CodeRedemption,
    LedgerEntry,
    LedgerTransaction,
    SystemWallet,
    TopUpCode,
    TxType,
    Wallet,
)
from app.services import audit_service

WELCOME_GRANT_QC = 50_000
TOPUP_PRESETS_QC = (1_000, 5_000, 10_000)
DAILY_TOPUP_CAP_QC = 50_000
MAX_ADMIN_GRANT_QC = 1_000_000
COMMISSION_BPS = 500  # 5 %
PIN_MAX_ATTEMPTS = 5
PIN_LOCK = timedelta(minutes=15)
#: Philippine time (no DST), for "today" in the daily top-up cap.
MANILA = timezone(timedelta(hours=8), "Asia/Manila")

CATEGORY_TYPES: dict[str, set[str]] = {
    "payments": {TxType.PAYMENT},
    "refunds": {TxType.REFUND, TxType.REVERSAL},
    "topups": {TxType.TOPUP, TxType.VOUCHER_REDEEM, TxType.GRANT},
    "earnings": {TxType.ESCROW_RELEASE, TxType.WITHDRAWAL},
}
SYSTEM_LABELS = {
    SystemWallet.ISSUANCE: "Queneth credit issuance",
    SystemWallet.ESCROW: "Queneth escrow",
    SystemWallet.PLATFORM_REVENUE: "Queneth commission",
    SystemWallet.OUT_SIMULATED: "Simulated payout",
}


# ─── Errors ────────────────────────────────────────────────────────────────


class InsufficientFunds(AppError):
    status_code = 409
    code = "insufficient_funds"
    message = "Not enough QC in your wallet."


class WalletLocked(AppError):
    status_code = 423
    code = "wallet_locked"
    message = "Too many wrong PINs. Your wallet is locked for 15 minutes."


class WrongPin(AppError):
    status_code = 403
    code = "wrong_pin"
    message = "That PIN isn't right."


class IdempotencyConflict(Conflict):
    code = "idempotency_key_reused"
    message = "This request key was already used for a different payment."


# ─── Wallet lookup ─────────────────────────────────────────────────────────


async def ensure_system_wallets(session: AsyncSession) -> None:
    """Create any missing system wallet (the migration seeds them on Postgres)."""
    have = set(
        (
            await session.scalars(select(Wallet.system_code).where(Wallet.owner_type == "system"))
        ).all()
    )
    for code in SystemWallet:
        if code.value not in have:
            session.add(Wallet(owner_type="system", system_code=code.value, balance_qc=0))
    await session.flush()


async def system_wallet(session: AsyncSession, code: SystemWallet) -> Wallet:
    wallet = await session.scalar(select(Wallet).where(Wallet.system_code == code.value))
    if wallet is None:
        await ensure_system_wallets(session)
        wallet = await session.scalar(select(Wallet).where(Wallet.system_code == code.value))
    assert wallet is not None
    return wallet


async def user_wallet(session: AsyncSession, user_id: uuid.UUID) -> Wallet:
    """The user's wallet, created on first use."""
    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == user_id))
    if wallet is not None:
        return wallet
    try:
        async with session.begin_nested():
            wallet = Wallet(owner_type="user", user_id=user_id, balance_qc=0)
            session.add(wallet)
    except IntegrityError:  # created concurrently by another request
        wallet = await session.scalar(select(Wallet).where(Wallet.user_id == user_id))
    assert wallet is not None
    return wallet


def commission_for(gross_qc: int) -> int:
    """5 % platform commission, rounded half up to whole QC (integer math only)."""
    return (gross_qc * COMMISSION_BPS + 5_000) // 10_000


def _reference(now: datetime) -> str:
    return f"QW{now.astimezone(MANILA):%Y%m%d}{secrets.randbelow(10**6):06d}"


# ─── The single posting primitive ──────────────────────────────────────────


async def post(
    session: AsyncSession,
    *,
    type: TxType,
    legs: list[tuple[uuid.UUID, int]],
    idempotency_key: str,
    memo: str | None = None,
    actor_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    reverses_id: uuid.UUID | None = None,
) -> LedgerTransaction:
    """Record one balanced movement. Must run inside `atomic(session)`.

    `legs` are (wallet_id, signed amount) pairs and must sum to zero.
    Returns the existing transaction if this idempotency key was used before.
    """
    if len(legs) < 2 or sum(a for _, a in legs) != 0 or any(a == 0 for _, a in legs):
        raise ValueError("A ledger transaction needs ≥ 2 non-zero legs that sum to zero.")
    existing = await session.scalar(
        select(LedgerTransaction).where(LedgerTransaction.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing

    # Flush first: the locking re-read below (populate_existing) would otherwise
    # discard unflushed changes on these wallet objects (e.g. a PIN just set).
    await session.flush()
    ids = sorted({wid for wid, _ in legs})
    locked = {
        w.id: w
        for w in (
            await session.scalars(
                select(Wallet)
                .where(Wallet.id.in_(ids))
                .order_by(Wallet.id)  # fixed lock order: no deadlocks
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    }
    if len(locked) != len(ids):
        raise NotFound("Wallet not found.", code="wallet_not_found")

    now = utcnow()
    tx = LedgerTransaction(
        id=uuid.uuid4(),
        type=type.value,
        reference=_reference(now),
        idempotency_key=idempotency_key,
        memo=memo,
        actor_id=actor_id,
        meta=meta or {},
        reverses_id=reverses_id,
        created_at=now,
    )
    session.add(tx)
    for wallet_id, amount in legs:
        wallet = locked[wallet_id]
        new_balance = wallet.balance_qc + amount
        if new_balance < 0 and wallet.system_code != SystemWallet.ISSUANCE.value:
            raise InsufficientFunds(
                details={"needed_qc": -amount, "available_qc": wallet.balance_qc}
            )
        wallet.balance_qc = new_balance
        session.add(
            LedgerEntry(
                transaction_id=tx.id,
                wallet_id=wallet.id,
                amount_qc=amount,
                balance_after_qc=new_balance,
                created_at=now,
            )
        )
    await session.flush()
    return tx


async def _idempotent(
    session: AsyncSession,
    key: str,
    work: Callable[[], Awaitable[LedgerTransaction]],
    *,
    expect_type: TxType,
    expect_wallet: uuid.UUID,
    expect_amount: int,
) -> LedgerTransaction:
    """Run `work` atomically. A replayed key returns the original transaction;
    the same key with a different payload is refused (409)."""

    async def check(tx: LedgerTransaction) -> LedgerTransaction:
        await session.refresh(tx, ["entries"])
        mine = sum(e.amount_qc for e in tx.entries if e.wallet_id == expect_wallet)
        if tx.type != expect_type.value or mine != expect_amount:
            raise IdempotencyConflict()
        return tx

    prior = await session.scalar(
        select(LedgerTransaction).where(LedgerTransaction.idempotency_key == key)
    )
    if prior is not None:
        return await check(prior)
    try:
        async with atomic(session):
            tx = await work()
    except IntegrityError:
        # Lost a race with the same key: the other request committed first.
        await session.rollback()
        prior = await session.scalar(
            select(LedgerTransaction).where(LedgerTransaction.idempotency_key == key)
        )
        if prior is None:
            raise
        return await check(prior)
    return tx


def _notify(session: AsyncSession, user_id: uuid.UUID, title: str, body: str) -> None:
    session.add(
        Notification(
            user_id=user_id,
            type="wallet.credited",
            payload={"title": title, "body": body, "action_url": "/account/wallet"},
        )
    )


# ─── Credits in: welcome grant, top-ups, codes, admin grants ───────────────


async def grant_welcome(session: AsyncSession, user: User) -> LedgerTransaction:
    """50,000 QC on sign-up so testers can shop right away (idempotent per user)."""
    wallet = await user_wallet(session, user.id)
    issuance = await system_wallet(session, SystemWallet.ISSUANCE)
    key = f"welcome:{user.id}"

    async def work() -> LedgerTransaction:
        tx = await post(
            session,
            type=TxType.GRANT,
            legs=[(issuance.id, -WELCOME_GRANT_QC), (wallet.id, WELCOME_GRANT_QC)],
            idempotency_key=key,
            memo="Welcome to Queneth",
            meta={"kind": "welcome"},
        )
        _notify(
            session,
            user.id,
            "Welcome credits added",
            f"QC {WELCOME_GRANT_QC:,} is in your QueWallet.",
        )
        return tx

    return await _idempotent(
        session,
        key,
        work,
        expect_type=TxType.GRANT,
        expect_wallet=wallet.id,
        expect_amount=WELCOME_GRANT_QC,
    )


def _manila_day_start(now: datetime) -> datetime:
    local = now.astimezone(MANILA)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


async def topped_up_today(session: AsyncSession, wallet_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount_qc), 0))
        .join(LedgerTransaction, LedgerTransaction.id == LedgerEntry.transaction_id)
        .where(
            LedgerEntry.wallet_id == wallet_id,
            LedgerTransaction.type == TxType.TOPUP.value,
            LedgerEntry.created_at >= _manila_day_start(utcnow()),
        )
    )
    return int(total or 0)


async def topup(session: AsyncSession, user: User, amount_qc: int, key: str) -> LedgerTransaction:
    """Simulated "Load credits": preset amounts, max 50,000 QC per Manila day."""
    assert_can(user, Permission.WALLET_TOPUP)
    if amount_qc not in TOPUP_PRESETS_QC:
        raise ValidationFailed(
            "Choose one of the preset amounts.",
            code="invalid_amount",
            details={"presets": list(TOPUP_PRESETS_QC)},
        )
    wallet = await user_wallet(session, user.id)
    issuance = await system_wallet(session, SystemWallet.ISSUANCE)
    full_key = f"topup:{user.id}:{key}"

    async def work() -> LedgerTransaction:
        # Lock the user's wallet first so two parallel top-ups can't both pass the cap.
        await session.execute(select(Wallet.id).where(Wallet.id == wallet.id).with_for_update())
        today = await topped_up_today(session, wallet.id)
        if today + amount_qc > DAILY_TOPUP_CAP_QC:
            raise Conflict(
                "Daily top-up limit reached. "
                f"You can add QC {DAILY_TOPUP_CAP_QC - today:,} more today.",
                code="daily_cap_reached",
                details={"remaining_qc": DAILY_TOPUP_CAP_QC - today},
            )
        tx = await post(
            session,
            type=TxType.TOPUP,
            legs=[(issuance.id, -amount_qc), (wallet.id, amount_qc)],
            idempotency_key=full_key,
            memo="Simulated top-up",
            actor_id=user.id,
        )
        _notify(
            session, user.id, "Credits loaded", f"QC {amount_qc:,} was added to your QueWallet."
        )
        return tx

    return await _idempotent(
        session,
        full_key,
        work,
        expect_type=TxType.TOPUP,
        expect_wallet=wallet.id,
        expect_amount=amount_qc,
    )


def normalize_code(raw: str) -> str:
    """Postel's Law: ' que demo-5000 ' → 'QUE-DEMO-5000'."""
    cleaned = "".join(ch for ch in raw.upper() if ch.isalnum() or ch in "- ").strip()
    return "-".join(part for part in cleaned.replace(" ", "-").split("-") if part)


async def redeem(session: AsyncSession, user: User, raw_code: str) -> LedgerTransaction:
    assert_can(user, Permission.WALLET_TOPUP)
    code_text = normalize_code(raw_code)
    wallet = await user_wallet(session, user.id)
    issuance = await system_wallet(session, SystemWallet.ISSUANCE)
    code = await session.scalar(select(TopUpCode).where(TopUpCode.code == code_text))
    if code is None:
        raise NotFound("We don't recognise that code.", code="code_not_found")
    key = f"redeem:{code.id}:{user.id}"
    if await session.scalar(
        select(CodeRedemption.id).where(
            CodeRedemption.code_id == code.id, CodeRedemption.user_id == user.id
        )
    ):
        raise Conflict("You've already redeemed this code.", code="code_already_redeemed")

    async def work() -> LedgerTransaction:
        locked = await session.scalar(
            select(TopUpCode)
            .where(TopUpCode.id == code.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        assert locked is not None
        if not locked.is_active or (locked.expires_at and as_aware(locked.expires_at) <= utcnow()):
            raise Conflict("This code has expired.", code="code_expired")
        if locked.used_count >= locked.max_uses:
            raise Conflict("This code has been fully redeemed.", code="code_exhausted")
        tx = await post(
            session,
            type=TxType.VOUCHER_REDEEM,
            legs=[(issuance.id, -locked.amount_qc), (wallet.id, locked.amount_qc)],
            idempotency_key=key,
            memo=f"Redeemed {locked.code}",
            actor_id=user.id,
            meta={"code": locked.code},
        )
        locked.used_count += 1
        session.add(CodeRedemption(code_id=locked.id, user_id=user.id, transaction_id=tx.id))
        _notify(
            session,
            user.id,
            "Code redeemed",
            f"QC {locked.amount_qc:,} was added with {locked.code}.",
        )
        return tx

    return await _idempotent(
        session,
        key,
        work,
        expect_type=TxType.VOUCHER_REDEEM,
        expect_wallet=wallet.id,
        expect_amount=code.amount_qc,
    )


async def admin_grant(
    session: AsyncSession,
    admin: User,
    target_email: str,
    amount_qc: int,
    reason: str,
    key: str,
    ip: str | None,
) -> LedgerTransaction:
    assert_can(admin, Permission.WALLET_GRANT)
    if not 1 <= amount_qc <= MAX_ADMIN_GRANT_QC:
        raise ValidationFailed(f"Grants are 1 to {MAX_ADMIN_GRANT_QC:,} QC.", code="invalid_amount")
    target = await session.scalar(select(User).where(User.email == target_email.strip().lower()))
    if target is None:
        raise NotFound("No user with that email.", code="user_not_found")
    wallet = await user_wallet(session, target.id)
    issuance = await system_wallet(session, SystemWallet.ISSUANCE)
    full_key = f"grant:{admin.id}:{key}"

    async def work() -> LedgerTransaction:
        tx = await post(
            session,
            type=TxType.GRANT,
            legs=[(issuance.id, -amount_qc), (wallet.id, amount_qc)],
            idempotency_key=full_key,
            memo=reason,
            actor_id=admin.id,
            meta={"kind": "admin_grant"},
        )
        audit_service.record(
            session,
            actor_id=admin.id,
            action="wallet.granted",
            target_type="user",
            target_id=target.id,
            after={"amount_qc": amount_qc, "transaction": tx.reference},
            reason=reason,
            ip=ip,
        )
        _notify(session, target.id, "Credits granted", f"QC {amount_qc:,} from Queneth: {reason}")
        return tx

    return await _idempotent(
        session,
        full_key,
        work,
        expect_type=TxType.GRANT,
        expect_wallet=wallet.id,
        expect_amount=amount_qc,
    )


async def create_code(
    session: AsyncSession,
    admin: User,
    *,
    amount_qc: int,
    max_uses: int,
    expires_at: datetime | None,
    code: str | None,
    memo: str | None,
    ip: str | None,
) -> TopUpCode:
    assert_can(admin, Permission.WALLET_GRANT)
    text = (
        normalize_code(code)
        if code
        else f"QUE-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
    )
    if await session.scalar(select(TopUpCode.id).where(TopUpCode.code == text)):
        raise Conflict("That code already exists.", code="code_exists")
    row = TopUpCode(
        code=text,
        amount_qc=amount_qc,
        max_uses=max_uses,
        expires_at=expires_at,
        memo=memo,
        created_by=admin.id,
    )
    async with atomic(session):
        session.add(row)
        await session.flush()
        audit_service.record(
            session,
            actor_id=admin.id,
            action="wallet.code_created",
            target_type="topup_code",
            target_id=row.id,
            after={"code": text, "amount_qc": amount_qc, "max_uses": max_uses},
            reason=memo,
            ip=ip,
        )
    return row


# ─── PIN ───────────────────────────────────────────────────────────────────


def _clean_pin(pin: str) -> str:
    digits = "".join(ch for ch in pin if not ch.isspace())  # Postel: "123 456"
    if len(digits) != 6 or not digits.isdigit():
        raise ValidationFailed("Your PIN is 6 digits.", code="invalid_pin")
    return digits


async def set_pin(session: AsyncSession, user: User, pin: str) -> None:
    assert_can(user, Permission.WALLET_VIEW)
    wallet = await user_wallet(session, user.id)
    if wallet.pin_hash:
        raise Conflict("You already have a PIN. Change it instead.", code="pin_exists")
    wallet.pin_hash = hash_password(_clean_pin(pin))
    await session.commit()


async def verify_pin(session: AsyncSession, wallet: Wallet, pin: str) -> None:
    """Raise unless `pin` is right. 5 wrong tries lock the wallet for 15 minutes.
    Failed attempts are committed even though the caller's action is refused."""
    if wallet.pin_hash is None:
        raise Conflict("Set a QueWallet PIN first.", code="pin_not_set")
    now = utcnow()
    if wallet.pin_locked_until and as_aware(wallet.pin_locked_until) > now:
        raise WalletLocked(details={"locked_until": as_aware(wallet.pin_locked_until).isoformat()})
    try:
        ok = verify_password(_clean_pin(pin), wallet.pin_hash)
    except ValidationFailed:
        ok = False
    if ok:
        if wallet.pin_failed_attempts:
            wallet.pin_failed_attempts = 0
            wallet.pin_locked_until = None
        return
    wallet.pin_failed_attempts += 1
    remaining = PIN_MAX_ATTEMPTS - wallet.pin_failed_attempts
    if remaining <= 0:
        wallet.pin_failed_attempts = 0
        wallet.pin_locked_until = now + PIN_LOCK
        await session.commit()
        raise WalletLocked(details={"locked_until": wallet.pin_locked_until.isoformat()})
    await session.commit()
    raise WrongPin(
        f"That PIN isn't right. {remaining} {'try' if remaining == 1 else 'tries'} left.",
        details={"attempts_remaining": remaining},
    )


async def change_pin(session: AsyncSession, user: User, current: str, new: str) -> None:
    assert_can(user, Permission.WALLET_VIEW)
    wallet = await user_wallet(session, user.id)
    await verify_pin(session, wallet, current)
    wallet.pin_hash = hash_password(_clean_pin(new))
    await session.commit()


# ─── Escrow primitives (Phase 6 checkout, Phase 7 fulfilment) ──────────────
# These run inside the caller's atomic() block.


async def pay_into_escrow(
    session: AsyncSession,
    buyer_id: uuid.UUID,
    amount_qc: int,
    key: str,
    *,
    memo: str,
    meta: dict[str, Any],
) -> LedgerTransaction:
    """Buyer → ESCROW. Raises InsufficientFunds when the wallet is short."""
    wallet = await user_wallet(session, buyer_id)
    escrow = await system_wallet(session, SystemWallet.ESCROW)
    return await post(
        session,
        type=TxType.PAYMENT,
        legs=[(wallet.id, -amount_qc), (escrow.id, amount_qc)],
        idempotency_key=key,
        memo=memo,
        actor_id=buyer_id,
        meta=meta,
    )


async def release_escrow(
    session: AsyncSession,
    seller_user_id: uuid.UUID,
    gross_qc: int,
    key: str,
    *,
    memo: str,
    meta: dict[str, Any],
) -> tuple[LedgerTransaction, LedgerTransaction]:
    """ESCROW → seller (gross − 5 %) and ESCROW → PLATFORM_REVENUE (5 %)."""
    commission = commission_for(gross_qc)
    seller = await user_wallet(session, seller_user_id)
    escrow = await system_wallet(session, SystemWallet.ESCROW)
    revenue = await system_wallet(session, SystemWallet.PLATFORM_REVENUE)
    release = await post(
        session,
        type=TxType.ESCROW_RELEASE,
        legs=[(escrow.id, -(gross_qc - commission)), (seller.id, gross_qc - commission)],
        idempotency_key=f"{key}:release",
        memo=memo,
        meta={**meta, "gross_qc": gross_qc, "commission_qc": commission},
    )
    fee = await post(
        session,
        type=TxType.COMMISSION,
        legs=[(escrow.id, -commission), (revenue.id, commission)],
        idempotency_key=f"{key}:commission",
        memo=f"5% commission · {memo}",
        meta={**meta, "gross_qc": gross_qc},
    )
    return release, fee


async def refund_escrow(
    session: AsyncSession,
    buyer_id: uuid.UUID,
    amount_qc: int,
    key: str,
    *,
    memo: str,
    meta: dict[str, Any],
) -> LedgerTransaction:
    wallet = await user_wallet(session, buyer_id)
    escrow = await system_wallet(session, SystemWallet.ESCROW)
    return await post(
        session,
        type=TxType.REFUND,
        legs=[(escrow.id, -amount_qc), (wallet.id, amount_qc)],
        idempotency_key=key,
        memo=memo,
        meta=meta,
    )


async def withdraw(
    session: AsyncSession, seller: User, amount_qc: int, pin: str, key: str
) -> LedgerTransaction:
    """Simulated payout: seller wallet → OUT_SIMULATED. PIN required."""
    assert_can(seller, Permission.EARNINGS_VIEW)
    if amount_qc < 100:
        raise ValidationFailed("Withdraw at least QC 100.", code="invalid_amount")
    wallet = await user_wallet(session, seller.id)
    await verify_pin(session, wallet, pin)
    out = await system_wallet(session, SystemWallet.OUT_SIMULATED)
    full_key = f"withdraw:{seller.id}:{key}"

    async def work() -> LedgerTransaction:
        return await post(
            session,
            type=TxType.WITHDRAWAL,
            legs=[(wallet.id, -amount_qc), (out.id, amount_qc)],
            idempotency_key=full_key,
            memo="Simulated payout to bank",
            actor_id=seller.id,
        )

    return await _idempotent(
        session,
        full_key,
        work,
        expect_type=TxType.WITHDRAWAL,
        expect_wallet=wallet.id,
        expect_amount=-amount_qc,
    )


# ─── Corrections ───────────────────────────────────────────────────────────


async def reverse(
    session: AsyncSession, admin: User, tx_id: uuid.UUID, reason: str, ip: str | None
) -> LedgerTransaction:
    """Post the exact opposite of a transaction. Never edits the original."""
    assert_can(admin, Permission.WALLET_REVERSE)
    original = await session.get(LedgerTransaction, tx_id)
    if original is None:
        raise NotFound("Transaction not found.", code="transaction_not_found")
    if original.type == TxType.REVERSAL.value:
        raise Conflict(
            "A reversal can't itself be reversed. Post a new grant instead.",
            code="cannot_reverse_reversal",
        )
    if await session.scalar(
        select(LedgerTransaction.id).where(LedgerTransaction.reverses_id == original.id)
    ):
        raise Conflict("This transaction was already reversed.", code="already_reversed")
    legs = [(e.wallet_id, -e.amount_qc) for e in original.entries]

    async with atomic(session):
        tx = await post(
            session,
            type=TxType.REVERSAL,
            legs=legs,
            idempotency_key=f"reverse:{original.id}",
            memo=f"Reversal of {original.reference}: {reason}",
            actor_id=admin.id,
            meta={"reverses": original.reference},
            reverses_id=original.id,
        )
        audit_service.record(
            session,
            actor_id=admin.id,
            action="wallet.reversed",
            target_type="ledger_transaction",
            target_id=original.id,
            before={"reference": original.reference, "type": original.type},
            after={"reversal": tx.reference},
            reason=reason,
            ip=ip,
        )
    return tx


# ─── Reads ─────────────────────────────────────────────────────────────────


@dataclass
class Drift:
    wallet_id: uuid.UUID
    label: str
    cached_qc: int
    computed_qc: int


@dataclass
class ReconcileReport:
    wallets_checked: int
    transactions_checked: int
    drift: list[Drift]
    unbalanced_transactions: list[str]
    total_balance_qc: int

    @property
    def ok(self) -> bool:
        return not self.drift and not self.unbalanced_transactions and self.total_balance_qc == 0


def wallet_label(w: Wallet, user_email: str | None = None) -> str:
    if w.system_code:
        return SYSTEM_LABELS.get(SystemWallet(w.system_code), w.system_code)
    return user_email or "Customer wallet"


async def reconcile(session: AsyncSession) -> ReconcileReport:
    """Recompute every balance from its entries and report any drift (spec §8)."""
    sums = dict(
        (
            await session.execute(
                select(LedgerEntry.wallet_id, func.sum(LedgerEntry.amount_qc)).group_by(
                    LedgerEntry.wallet_id
                )
            )
        ).all()
    )
    wallets = list(
        (await session.scalars(select(Wallet).execution_options(populate_existing=True))).all()
    )
    drift = [
        Drift(w.id, wallet_label(w), w.balance_qc, int(sums.get(w.id, 0)))
        for w in wallets
        if w.balance_qc != int(sums.get(w.id, 0))
    ]
    unbalanced = [
        ref
        for ref, total in (
            await session.execute(
                select(LedgerTransaction.reference, func.sum(LedgerEntry.amount_qc))
                .join(LedgerEntry, LedgerEntry.transaction_id == LedgerTransaction.id)
                .group_by(LedgerTransaction.reference)
            )
        ).all()
        if int(total) != 0
    ]
    tx_count = await session.scalar(select(func.count()).select_from(LedgerTransaction)) or 0
    return ReconcileReport(
        wallets_checked=len(wallets),
        transactions_checked=tx_count,
        drift=drift,
        unbalanced_transactions=unbalanced,
        total_balance_qc=sum(w.balance_qc for w in wallets),
    )


def category_of(tx_type: str) -> str:
    for cat, types in CATEGORY_TYPES.items():
        if tx_type in types:
            return cat
    return "other"


async def history(
    session: AsyncSession,
    wallet_id: uuid.UUID,
    *,
    category: str | None,
    before: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[tuple[LedgerEntry, LedgerTransaction]]:
    stmt = (
        select(LedgerEntry, LedgerTransaction)
        .join(LedgerTransaction, LedgerTransaction.id == LedgerEntry.transaction_id)
        .where(LedgerEntry.wallet_id == wallet_id)
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
    )
    if category:
        stmt = stmt.where(LedgerTransaction.type.in_([t.value for t in CATEGORY_TYPES[category]]))
    if before:
        created, last = before
        stmt = stmt.where(
            (LedgerEntry.created_at < created)
            | ((LedgerEntry.created_at == created) & (LedgerEntry.id < last))
        )
    return [(e, t) for e, t in (await session.execute(stmt.limit(limit))).all()]


async def statement_csv(session: AsyncSession, user: User) -> str:
    assert_can(user, Permission.WALLET_VIEW)
    wallet = await user_wallet(session, user.id)
    rows = await history(session, wallet.id, category=None, before=None, limit=10_000)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["date_manila", "reference", "type", "description", "amount_qc", "balance_after_qc"]
    )
    for entry, tx in reversed(rows):
        writer.writerow(
            [
                entry.created_at.astimezone(MANILA).strftime("%Y-%m-%d %H:%M"),
                tx.reference,
                tx.type,
                tx.memo or "",
                entry.amount_qc,
                entry.balance_after_qc,
            ]
        )
    writer.writerow([])
    writer.writerow(
        ["QueWallet credits are simulated for academic purposes and have no cash value."]
    )
    return out.getvalue()
