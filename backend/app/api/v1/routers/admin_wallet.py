"""Control Room QueWallet tools: platform balances, reconciliation, demo credit
grants, voucher codes, the full ledger and reversals. Every write is
audit-logged with a reason. (The Control Room UI for these lands in Phase 9.)"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy import select

from app.api.deps import DbSession, client_ip, require_permission, require_role
from app.api.v1.routers.wallet import describe
from app.core.pagination import clamp_limit, decode_cursor, encode_cursor
from app.core.permissions import Permission, Role
from app.models.user import User
from app.models.wallet import LedgerTransaction, SystemWallet, TopUpCode, Wallet
from app.schemas.common import CursorPage
from app.schemas.wallet import (
    AdminTxOut,
    CodeCreate,
    CodeOut,
    DriftOut,
    GrantRequest,
    ReconcileOut,
    ReverseRequest,
    SystemBalance,
)
from app.services import wallet_service as ws

router = APIRouter(
    prefix="/admin/wallet", tags=["admin"], dependencies=[Depends(require_role(Role.ADMIN))]
)

Viewer = Depends(require_permission(Permission.WALLET_VIEW_PLATFORM))
Granter = Depends(require_permission(Permission.WALLET_GRANT))
Reverser = Depends(require_permission(Permission.WALLET_REVERSE))
IdemKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=80)]


async def admin_tx(session: DbSession, tx: LedgerTransaction) -> AdminTxOut:
    detail = await describe(session, tx, None)
    reversed_ = await session.scalar(
        select(LedgerTransaction.id).where(LedgerTransaction.reverses_id == tx.id)
    )
    return AdminTxOut(
        id=tx.id,
        reference=tx.reference,
        type=tx.type,
        memo=tx.memo,
        created_at=tx.created_at,
        total_qc=sum(e.amount_qc for e in tx.entries if e.amount_qc > 0),
        entries=detail.entries,
        reversed=reversed_ is not None,
    )


@router.get("/system", response_model=list[SystemBalance], summary="Platform wallet balances")
async def system_balances(session: DbSession, _: User = Viewer) -> list[SystemBalance]:
    await ws.ensure_system_wallets(session)
    rows = (await session.scalars(select(Wallet).where(Wallet.owner_type == "system"))).all()
    order = [c.value for c in SystemWallet]
    return [
        SystemBalance(code=w.system_code or "", label=ws.wallet_label(w), balance_qc=w.balance_qc)
        for w in sorted(rows, key=lambda w: order.index(w.system_code or ""))
    ]


@router.get(
    "/reconcile", response_model=ReconcileOut, summary="Recompute balances and report drift"
)
async def reconcile(session: DbSession, _: User = Viewer) -> ReconcileOut:
    r = await ws.reconcile(session)
    return ReconcileOut(
        ok=r.ok,
        wallets_checked=r.wallets_checked,
        transactions_checked=r.transactions_checked,
        total_balance_qc=r.total_balance_qc,
        drift=[DriftOut(**d.__dict__) for d in r.drift],
        unbalanced_transactions=r.unbalanced_transactions,
    )


@router.post(
    "/grants",
    response_model=AdminTxOut,
    status_code=status.HTTP_201_CREATED,
    summary="Grant demo credits",
)
async def grant(
    body: GrantRequest, key: IdemKey, request: Request, session: DbSession, admin: User = Granter
) -> AdminTxOut:
    tx = await ws.admin_grant(
        session, admin, body.email, body.amount_qc, body.reason, key, client_ip(request)
    )
    return await admin_tx(session, tx)


@router.get("/codes", response_model=list[CodeOut], summary="Top-up codes")
async def codes(session: DbSession, _: User = Viewer) -> list[CodeOut]:
    rows = (await session.scalars(select(TopUpCode).order_by(TopUpCode.created_at.desc()))).all()
    return [CodeOut.model_validate(c) for c in rows]


@router.post(
    "/codes", response_model=CodeOut, status_code=status.HTTP_201_CREATED, summary="Issue a code"
)
async def create_code(
    body: CodeCreate, request: Request, session: DbSession, admin: User = Granter
) -> CodeOut:
    row = await ws.create_code(
        session,
        admin,
        amount_qc=body.amount_qc,
        max_uses=body.max_uses,
        expires_at=body.expires_at,
        code=body.code,
        memo=body.memo,
        ip=client_ip(request),
    )
    return CodeOut.model_validate(row)


@router.get(
    "/transactions", response_model=CursorPage[AdminTxOut], summary="Full ledger, newest first"
)
async def ledger(
    session: DbSession,
    _: User = Viewer,
    type: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=96)] = None,
) -> CursorPage[AdminTxOut]:
    size = clamp_limit(limit)
    stmt = select(LedgerTransaction).order_by(
        LedgerTransaction.created_at.desc(), LedgerTransaction.id.desc()
    )
    if type:
        stmt = stmt.where(LedgerTransaction.type == type.upper())
    if pos := decode_cursor(cursor):
        at, last = datetime.fromisoformat(pos["at"]), uuid.UUID(pos["id"])
        stmt = stmt.where(
            (LedgerTransaction.created_at < at)
            | ((LedgerTransaction.created_at == at) & (LedgerTransaction.id < last))
        )
    rows = list((await session.scalars(stmt.limit(size + 1))).all())
    nxt = None
    if len(rows) > size:
        rows = rows[:size]
        nxt = encode_cursor({"at": rows[-1].created_at.isoformat(), "id": str(rows[-1].id)})
    return CursorPage[AdminTxOut](
        items=[await admin_tx(session, t) for t in rows], next_cursor=nxt, has_more=nxt is not None
    )


@router.post(
    "/transactions/{tx_id}/reverse",
    response_model=AdminTxOut,
    status_code=status.HTTP_201_CREATED,
    summary="Reverse a transaction (posts the opposite entries; never edits)",
)
async def reverse(
    tx_id: uuid.UUID,
    body: ReverseRequest,
    request: Request,
    session: DbSession,
    admin: User = Reverser,
) -> AdminTxOut:
    tx = await ws.reverse(session, admin, tx_id, body.reason, client_ip(request))
    return await admin_tx(session, tx)
