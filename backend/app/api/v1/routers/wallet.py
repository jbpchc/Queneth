"""QueWallet endpoints for buyers and sellers. Every money-moving POST takes an
`Idempotency-Key` header: retrying with the same key never moves money twice."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.core.errors import NotFound
from app.core.pagination import clamp_limit, decode_cursor, encode_cursor
from app.core.permissions import Permission
from app.core.rate_limit import limiter
from app.core.security import as_aware, utcnow
from app.models.user import User
from app.models.wallet import LedgerEntry, LedgerTransaction, Wallet
from app.schemas.common import CursorPage
from app.schemas.wallet import (
    Category,
    ChangePinRequest,
    EntryOut,
    LedgerLine,
    RedeemRequest,
    SetPinRequest,
    TopUpRequest,
    TransactionDetail,
    TxResult,
    WalletSummary,
    WithdrawRequest,
)
from app.services import wallet_service as ws
from app.services.studio_service import held_in_escrow

router = APIRouter(prefix="/wallet", tags=["wallet"])

WalletUser = Depends(require_permission(Permission.WALLET_VIEW))
IdemKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=80,
        description="Unique per attempt (e.g. a UUID). Reuse it to retry safely.",
    ),
]
WALLET_LIMIT = "10/minute"
PIN_LIMIT = "10/minute"


async def summary(session: DbSession, user: User) -> WalletSummary:
    wallet = await ws.user_wallet(session, user.id)
    today = await ws.topped_up_today(session, wallet.id)
    locked = as_aware(wallet.pin_locked_until) if wallet.pin_locked_until else None
    return WalletSummary(
        balance_qc=wallet.balance_qc,
        available_qc=wallet.balance_qc,
        pending_qc=await held_in_escrow(session, user.seller_id) if user.seller_id else 0,
        has_pin=wallet.pin_hash is not None,
        locked_until=locked if locked and locked > utcnow() else None,
        topup_presets_qc=list(ws.TOPUP_PRESETS_QC),
        topup_today_qc=today,
        topup_remaining_today_qc=max(0, ws.DAILY_TOPUP_CAP_QC - today),
        daily_topup_cap_qc=ws.DAILY_TOPUP_CAP_QC,
    )


def line(entry: LedgerEntry, tx: LedgerTransaction) -> LedgerLine:
    return LedgerLine(
        transaction_id=tx.id,
        reference=tx.reference,
        type=tx.type,
        category=ws.category_of(tx.type),
        memo=tx.memo,
        amount_qc=entry.amount_qc,
        balance_after_qc=entry.balance_after_qc,
        created_at=entry.created_at,
    )


async def _result(session: DbSession, user: User, tx: LedgerTransaction) -> TxResult:
    wallet = await ws.user_wallet(session, user.id)
    await session.refresh(tx, ["entries"])  # a just-posted tx has no loaded entries
    entry = next(e for e in tx.entries if e.wallet_id == wallet.id)
    return TxResult(transaction=line(entry, tx), wallet=await summary(session, user))


@router.get("", response_model=WalletSummary, summary="Balance, PIN state and top-up allowance")
async def get_wallet(session: DbSession, user: User = WalletUser) -> WalletSummary:
    out = await summary(session, user)
    await session.commit()  # persists a lazily created wallet
    return out


@router.post(
    "/pin", status_code=status.HTTP_204_NO_CONTENT, summary="Set your 6-digit PIN (first use)"
)
@limiter.limit(PIN_LIMIT)
async def set_pin(
    request: Request, body: SetPinRequest, session: DbSession, user: User = WalletUser
) -> None:
    await ws.set_pin(session, user, body.pin)


@router.put("/pin", status_code=status.HTTP_204_NO_CONTENT, summary="Change your PIN")
@limiter.limit(PIN_LIMIT)
async def change_pin(
    request: Request, body: ChangePinRequest, session: DbSession, user: User = WalletUser
) -> None:
    await ws.change_pin(session, user, body.current_pin, body.new_pin)


@router.post(
    "/topups",
    response_model=TxResult,
    status_code=status.HTTP_201_CREATED,
    summary="Simulated top-up",
)
@limiter.limit(WALLET_LIMIT)
async def topup(
    request: Request, body: TopUpRequest, key: IdemKey, session: DbSession, user: User = WalletUser
) -> TxResult:
    tx = await ws.topup(session, user, body.amount_qc, key)
    return await _result(session, user, tx)


@router.post(
    "/redeem",
    response_model=TxResult,
    status_code=status.HTTP_201_CREATED,
    summary="Redeem a QueWallet code",
)
@limiter.limit(WALLET_LIMIT)
async def redeem(
    request: Request, body: RedeemRequest, session: DbSession, user: User = WalletUser
) -> TxResult:
    tx = await ws.redeem(session, user, body.code)
    return await _result(session, user, tx)


@router.post(
    "/withdrawals",
    response_model=TxResult,
    status_code=status.HTTP_201_CREATED,
    summary="Simulated seller payout",
)
@limiter.limit(WALLET_LIMIT)
async def withdraw(
    request: Request,
    body: WithdrawRequest,
    key: IdemKey,
    session: DbSession,
    user: User = Depends(require_permission(Permission.EARNINGS_VIEW)),
) -> TxResult:
    tx = await ws.withdraw(session, user, body.amount_qc, body.pin, key)
    return await _result(session, user, tx)


@router.get(
    "/transactions", response_model=CursorPage[LedgerLine], summary="Your history, newest first"
)
async def transactions(
    session: DbSession,
    user: User = WalletUser,
    category: Category | None = None,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=96)] = None,
) -> CursorPage[LedgerLine]:
    wallet = await ws.user_wallet(session, user.id)
    pos = decode_cursor(cursor)
    before = (datetime.fromisoformat(pos["at"]), uuid.UUID(pos["id"])) if pos else None
    size = clamp_limit(limit)
    rows = await ws.history(session, wallet.id, category=category, before=before, limit=size + 1)
    nxt = None
    if len(rows) > size:
        rows = rows[:size]
        last = rows[-1][0]
        nxt = encode_cursor({"at": last.created_at.isoformat(), "id": str(last.id)})
    return CursorPage[LedgerLine](
        items=[line(e, t) for e, t in rows], next_cursor=nxt, has_more=nxt is not None
    )


async def describe(
    session: DbSession, tx: LedgerTransaction, me: Wallet | None
) -> TransactionDetail:
    await session.refresh(tx, ["entries"])
    owners = {
        w.id: (w, email)
        for w, email in (
            await session.execute(
                select(Wallet, User.email)
                .outerjoin(User, User.id == Wallet.user_id)
                .where(Wallet.id.in_([e.wallet_id for e in tx.entries]))
            )
        ).all()
    }
    reversed_by = await session.scalar(
        select(LedgerTransaction.reference).where(LedgerTransaction.reverses_id == tx.id)
    )
    reverses = (
        await session.scalar(
            select(LedgerTransaction.reference).where(LedgerTransaction.id == tx.reverses_id)
        )
        if tx.reverses_id
        else None
    )
    entries = []
    for e in tx.entries:
        w, email = owners[e.wallet_id]
        mine = me is not None and w.id == me.id
        entries.append(
            EntryOut(
                wallet="Your QueWallet"
                if mine
                else ws.wallet_label(w, email if me is None else None),
                is_you=mine,
                amount_qc=e.amount_qc,
                # Other people's balances are never shown to a user.
                balance_after_qc=e.balance_after_qc if (mine or me is None) else None,
            )
        )
    return TransactionDetail(
        id=tx.id,
        reference=tx.reference,
        type=tx.type,
        category=ws.category_of(tx.type),
        memo=tx.memo,
        created_at=tx.created_at,
        entries=entries,
        reversed_by=reversed_by,
        reverses=reverses,
    )


@router.get(
    "/transactions/{tx_id}",
    response_model=TransactionDetail,
    summary="Every ledger entry of one transaction",
)
async def transaction(
    tx_id: uuid.UUID, session: DbSession, user: User = WalletUser
) -> TransactionDetail:
    wallet = await ws.user_wallet(session, user.id)
    tx = await session.get(LedgerTransaction, tx_id)
    # Owner-scoped: a transaction that never touched your wallet looks missing.
    if tx is None or all(e.wallet_id != wallet.id for e in tx.entries):
        raise NotFound("Transaction not found.", code="transaction_not_found")
    return await describe(session, tx, wallet)


@router.get(
    "/statement.csv",
    summary="Download your statement (CSV)",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
async def statement(session: DbSession, user: User = WalletUser) -> Response:
    body = await ws.statement_csv(session, user)
    stamp = utcnow().astimezone(ws.MANILA).strftime("%Y%m%d")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="quewallet-statement-{stamp}.csv"'},
    )
