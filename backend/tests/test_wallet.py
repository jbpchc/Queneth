"""QueWallet: double-entry ledger, idempotency, escrow, PIN, codes, reversals,
reconciliation (spec §8 and §12 testing list)."""

import asyncio
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app.core.security import hash_password, utcnow
from app.db.atomic import atomic
from app.models import (
    AuditLog,
    LedgerEntry,
    LedgerTransaction,
    SystemWallet,
    TopUpCode,
    Wallet,
)
from app.services import wallet_service as ws

W = "/api/v1/wallet"


def key() -> dict[str, str]:
    return {"Idempotency-Key": uuid.uuid4().hex}


async def balance(db, user) -> int:
    w = await db.scalar(
        select(Wallet).where(Wallet.user_id == user.id).execution_options(populate_existing=True)
    )
    return w.balance_qc if w else 0


async def system_balance(db, code: SystemWallet) -> int:
    w = await db.scalar(
        select(Wallet)
        .where(Wallet.system_code == code.value)
        .execution_options(populate_existing=True)
    )
    return w.balance_qc


async def assert_reconciled(db) -> None:
    report = await ws.reconcile(db)
    assert report.ok, report


@pytest.fixture
async def funded(db, accounts):
    """Buyer and seller each hold the 50,000 QC welcome grant; buyer PIN = 123456."""
    for u in (accounts.buyer, accounts.seller):
        await ws.grant_welcome(db, u)
    wallet = await ws.user_wallet(db, accounts.buyer.id)
    wallet.pin_hash = hash_password("123456")
    seller_wallet = await ws.user_wallet(db, accounts.seller.id)
    seller_wallet.pin_hash = hash_password("123456")
    await db.commit()
    return accounts


async def login(client, email):
    client.cookies.clear()
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": "Queneth#2026"})
    assert res.status_code == 200


# ─── Ledger basics ─────────────────────────────────────────────────────────


async def test_register_grants_welcome_credits(client, db):
    res = await client.post(
        "/api/v1/auth/register",
        json={"name": "Ana Santos", "email": "ana@example.com", "password": "silk2026x"},
    )
    assert res.status_code == 201
    w = (await client.get(W)).json()
    assert w["balance_qc"] == ws.WELCOME_GRANT_QC and w["has_pin"] is False
    assert await system_balance(db, SystemWallet.ISSUANCE) == -ws.WELCOME_GRANT_QC
    await assert_reconciled(db)


async def test_welcome_grant_is_idempotent(db, accounts):
    first = await ws.grant_welcome(db, accounts.buyer)
    second = await ws.grant_welcome(db, accounts.buyer)
    assert first.id == second.id
    assert await balance(db, accounts.buyer) == ws.WELCOME_GRANT_QC


async def test_every_transaction_balances(db, funded):
    for tx in (await db.scalars(select(LedgerTransaction))).all():
        assert sum(e.amount_qc for e in tx.entries) == 0
        assert len(tx.entries) >= 2


async def test_post_rejects_unbalanced_legs(db, funded):
    w = await ws.user_wallet(db, funded.buyer.id)
    issuance = await ws.system_wallet(db, SystemWallet.ISSUANCE)
    with pytest.raises(ValueError):
        async with atomic(db):
            await ws.post(
                db,
                type=ws.TxType.GRANT,
                legs=[(issuance.id, -100), (w.id, 90)],
                idempotency_key="bad",
            )


def test_commission_is_integer_and_rounds_half_up():
    assert ws.commission_for(10_000) == 500
    assert ws.commission_for(8_910) == 446  # 445.5 → 446
    assert ws.commission_for(1) == 0


# ─── Payments & escrow (primitives used by checkout) ───────────────────────


async def test_payment_escrow_release_with_commission(db, funded):
    buyer, seller = funded.buyer, funded.seller
    async with atomic(db):
        await ws.pay_into_escrow(
            db, buyer.id, 10_000, "order-1:pay", memo="Order QN-1", meta={"order": "QN-1"}
        )
    assert await balance(db, buyer) == 40_000
    assert await system_balance(db, SystemWallet.ESCROW) == 10_000

    async with atomic(db):
        release, fee = await ws.release_escrow(
            db, seller.id, 10_000, "order-1:sub-1", memo="QN-1", meta={}
        )
    assert await balance(db, seller) == 50_000 + 9_500
    assert await system_balance(db, SystemWallet.PLATFORM_REVENUE) == 500
    assert await system_balance(db, SystemWallet.ESCROW) == 0
    assert release.type == "ESCROW_RELEASE" and fee.type == "COMMISSION"
    await assert_reconciled(db)


async def test_refund_returns_escrow_to_buyer(db, funded):
    async with atomic(db):
        await ws.pay_into_escrow(db, funded.buyer.id, 7_500, "o2:pay", memo="QN-2", meta={})
    async with atomic(db):
        await ws.refund_escrow(db, funded.buyer.id, 7_500, "o2:refund", memo="QN-2", meta={})
    assert await balance(db, funded.buyer) == 50_000
    assert await system_balance(db, SystemWallet.ESCROW) == 0
    await assert_reconciled(db)


async def test_insufficient_funds_rolls_back_everything(db, funded):
    buyer_id = funded.buyer.id  # the rollback expires loaded objects
    with pytest.raises(ws.InsufficientFunds) as exc:
        async with atomic(db):
            await ws.pay_into_escrow(db, buyer_id, 50_001, "o3:pay", memo="QN-3", meta={})
    assert exc.value.details == {"needed_qc": 50_001, "available_qc": 50_000}
    w = await db.scalar(select(Wallet).where(Wallet.user_id == buyer_id))
    assert w.balance_qc == 50_000
    assert (
        await db.scalar(
            select(LedgerTransaction.id).where(LedgerTransaction.idempotency_key == "o3:pay")
        )
        is None
    )
    await assert_reconciled(db)


async def test_payment_retry_with_same_key_never_charges_twice(db, funded):
    async with atomic(db):
        first = await ws.pay_into_escrow(db, funded.buyer.id, 5_000, "o4:pay", memo="QN-4", meta={})
    async with atomic(db):
        again = await ws.pay_into_escrow(db, funded.buyer.id, 5_000, "o4:pay", memo="QN-4", meta={})
    assert first.id == again.id
    assert await balance(db, funded.buyer) == 45_000


@pytest.mark.postgres
async def test_concurrent_double_spend_is_impossible(session_factory, funded):
    """Two payments of 30,000 against 50,000 race; row locks let exactly one win."""

    async def pay(k: str) -> str:
        async with session_factory() as s:
            try:
                async with atomic(s):
                    await ws.pay_into_escrow(s, funded.buyer.id, 30_000, k, memo="race", meta={})
                return "ok"
            except ws.InsufficientFunds:
                return "insufficient"

    results = await asyncio.gather(pay("race-a"), pay("race-b"))
    assert sorted(results) == ["insufficient", "ok"]
    async with session_factory() as s:
        assert await balance(s, funded.buyer) == 20_000
        await assert_reconciled(s)


# ─── Top-ups ───────────────────────────────────────────────────────────────


async def test_topup_presets_cap_and_idempotency(client, funded):
    await login(client, "buyer@queneth.test")
    assert (
        await client.post(f"{W}/topups", json={"amount_qc": 2_000}, headers=key())
    ).status_code == 422
    assert (
        await client.post(f"{W}/topups", json={"amount_qc": 5_000})
    ).status_code == 422  # no key

    k = key()
    first = await client.post(f"{W}/topups", json={"amount_qc": 10_000}, headers=k)
    retry = await client.post(f"{W}/topups", json={"amount_qc": 10_000}, headers=k)
    assert first.status_code == retry.status_code == 201
    assert first.json()["transaction"]["reference"] == retry.json()["transaction"]["reference"]
    assert retry.json()["wallet"]["balance_qc"] == 60_000

    clash = await client.post(f"{W}/topups", json={"amount_qc": 5_000}, headers=k)
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "idempotency_key_reused"

    for _ in range(4):  # 10k + 4×10k = 50k, the daily cap
        assert (
            await client.post(f"{W}/topups", json={"amount_qc": 10_000}, headers=key())
        ).status_code == 201
    over = await client.post(f"{W}/topups", json={"amount_qc": 1_000}, headers=key())
    assert over.status_code == 409 and over.json()["error"]["code"] == "daily_cap_reached"
    w = (await client.get(W)).json()
    assert w["topup_today_qc"] == 50_000 and w["topup_remaining_today_qc"] == 0


async def test_admin_cannot_top_up(client, funded):
    await login(client, "admin@queneth.test")
    assert (
        await client.post(f"{W}/topups", json={"amount_qc": 1_000}, headers=key())
    ).status_code == 403


# ─── Codes ─────────────────────────────────────────────────────────────────


async def test_redeem_code_rules(client, db, funded):
    db.add_all(
        [
            TopUpCode(code="QUE-DEMO-5000", amount_qc=5_000, max_uses=1),
            TopUpCode(
                code="QUE-OLD-1000",
                amount_qc=1_000,
                max_uses=5,
                expires_at=utcnow() - timedelta(days=1),
            ),
        ]
    )
    await db.commit()
    await login(client, "buyer@queneth.test")
    ok = await client.post(f"{W}/redeem", json={"code": "  que demo-5000 "})  # Postel's Law
    assert ok.status_code == 201 and ok.json()["wallet"]["balance_qc"] == 55_000
    again = await client.post(f"{W}/redeem", json={"code": "QUE-DEMO-5000"})
    assert again.json()["error"]["code"] == "code_already_redeemed"
    assert (await client.post(f"{W}/redeem", json={"code": "QUE-OLD-1000"})).json()["error"][
        "code"
    ] == "code_expired"
    assert (await client.post(f"{W}/redeem", json={"code": "NOPE-0000"})).status_code == 404

    # Seller accounts don't top up: their wallet only holds what they earn.
    await login(client, "seller@queneth.test")
    assert (await client.post(f"{W}/redeem", json={"code": "QUE-DEMO-5000"})).status_code == 403

    client.cookies.clear()
    second = {"name": "Ana Cruz", "email": "ana@queneth.test", "password": "Queneth#2026"}
    assert (await client.post("/api/v1/auth/register", json=second)).status_code == 201
    exhausted = await client.post(f"{W}/redeem", json={"code": "QUE-DEMO-5000"})
    assert exhausted.json()["error"]["code"] == "code_exhausted"
    await assert_reconciled(db)


# ─── PIN ───────────────────────────────────────────────────────────────────


async def test_pin_set_change_and_lockout(client, db, accounts):
    await login(client, "buyer@queneth.test")
    assert (await client.post(f"{W}/pin", json={"pin": "12345"})).status_code == 422
    assert (await client.post(f"{W}/pin", json={"pin": "246 810"})).status_code == 204
    assert (await client.post(f"{W}/pin", json={"pin": "111111"})).json()["error"][
        "code"
    ] == "pin_exists"
    assert (await client.get(W)).json()["has_pin"] is True

    for remaining in (4, 3, 2, 1):
        res = await client.put(f"{W}/pin", json={"current_pin": "000000", "new_pin": "135790"})
        assert res.status_code == 403
        assert res.json()["error"]["details"]["attempts_remaining"] == remaining
    locked = await client.put(f"{W}/pin", json={"current_pin": "000000", "new_pin": "135790"})
    assert locked.status_code == 423 and locked.json()["error"]["code"] == "wallet_locked"
    # Even the right PIN is refused while locked.
    still = await client.put(f"{W}/pin", json={"current_pin": "246810", "new_pin": "135790"})
    assert still.status_code == 423
    assert (await client.get(W)).json()["locked_until"] is not None

    wallet = await db.scalar(select(Wallet).where(Wallet.user_id == accounts.buyer.id))
    await db.execute(
        update(Wallet)
        .where(Wallet.id == wallet.id)
        .values(pin_locked_until=utcnow() - timedelta(seconds=1))
    )
    await db.commit()
    ok = await client.put(f"{W}/pin", json={"current_pin": "246810", "new_pin": "135790"})
    assert ok.status_code == 204


# ─── Withdrawals ───────────────────────────────────────────────────────────


async def test_seller_withdrawal_needs_pin(client, db, funded):
    await login(client, "seller@queneth.test")
    bad = await client.post(
        f"{W}/withdrawals", json={"amount_qc": 1_000, "pin": "999999"}, headers=key()
    )
    assert bad.status_code == 403
    ok = await client.post(
        f"{W}/withdrawals", json={"amount_qc": 1_000, "pin": "123456"}, headers=key()
    )
    assert ok.status_code == 201 and ok.json()["wallet"]["balance_qc"] == 49_000
    assert await system_balance(db, SystemWallet.OUT_SIMULATED) == 1_000
    too_much = await client.post(
        f"{W}/withdrawals", json={"amount_qc": 60_000, "pin": "123456"}, headers=key()
    )
    assert too_much.json()["error"]["code"] == "insufficient_funds"

    await login(client, "buyer@queneth.test")
    assert (
        await client.post(
            f"{W}/withdrawals", json={"amount_qc": 1_000, "pin": "123456"}, headers=key()
        )
    ).status_code == 403
    await assert_reconciled(db)


# ─── History, detail, statement ────────────────────────────────────────────


async def test_history_detail_and_owner_scoping(client, db, funded):
    async with atomic(db):
        await ws.pay_into_escrow(db, funded.buyer.id, 3_000, "o5:pay", memo="Order QN-5", meta={})
    await login(client, "buyer@queneth.test")
    all_ = (await client.get(f"{W}/transactions")).json()["items"]
    assert [i["type"] for i in all_] == ["PAYMENT", "GRANT"]
    assert all_[0]["amount_qc"] == -3_000 and all_[0]["balance_after_qc"] == 47_000
    payments = (await client.get(f"{W}/transactions", params={"category": "payments"})).json()[
        "items"
    ]
    assert len(payments) == 1
    topups = (await client.get(f"{W}/transactions", params={"category": "topups"})).json()["items"]
    assert [i["type"] for i in topups] == ["GRANT"]

    detail = (await client.get(f"{W}/transactions/{payments[0]['transaction_id']}")).json()
    assert {e["wallet"] for e in detail["entries"]} == {"Your QueWallet", "Queneth escrow"}
    escrow_entry = next(e for e in detail["entries"] if not e["is_you"])
    assert escrow_entry["balance_after_qc"] is None  # never leak other balances

    await login(client, "seller@queneth.test")
    assert (
        await client.get(f"{W}/transactions/{payments[0]['transaction_id']}")
    ).status_code == 404


async def test_statement_csv(client, funded):
    await login(client, "buyer@queneth.test")
    res = await client.get(f"{W}/statement.csv")
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    lines = res.text.strip().splitlines()
    assert lines[0].startswith("date_manila,reference,type")
    assert ",GRANT," in lines[1] and lines[1].endswith(",50000,50000")
    assert "no cash value" in lines[-1]


# ─── Admin tools ───────────────────────────────────────────────────────────


async def test_admin_grant_reverse_and_audit(client, db, funded):
    await login(client, "buyer@queneth.test")
    denied = await client.post(
        "/api/v1/admin/wallet/grants",
        json={"email": "buyer@queneth.test", "amount_qc": 1_000, "reason": "Self-service"},
        headers=key(),
    )
    assert denied.status_code == 403  # non-admins can't grant credits

    await login(client, "admin@queneth.test")
    grant = await client.post(
        "/api/v1/admin/wallet/grants",
        json={"email": "BUYER@queneth.test", "amount_qc": 2_500, "reason": "Demo day credits"},
        headers=key(),
    )
    assert grant.status_code == 201, grant.text
    assert await balance(db, funded.buyer) == 52_500
    assert await db.scalar(select(AuditLog.id).where(AuditLog.action == "wallet.granted"))

    tx_id = grant.json()["id"]
    rev = await client.post(
        f"/api/v1/admin/wallet/transactions/{tx_id}/reverse", json={"reason": "Granted in error"}
    )
    assert rev.status_code == 201 and rev.json()["type"] == "REVERSAL"
    assert await balance(db, funded.buyer) == 50_000
    twice = await client.post(
        f"/api/v1/admin/wallet/transactions/{tx_id}/reverse", json={"reason": "Again please"}
    )
    assert twice.json()["error"]["code"] == "already_reversed"
    assert await db.scalar(select(AuditLog.id).where(AuditLog.action == "wallet.reversed"))

    # The original entries are untouched: reversal adds, never edits.
    original_entries = (
        await db.scalars(select(LedgerEntry).where(LedgerEntry.transaction_id == uuid.UUID(tx_id)))
    ).all()
    assert sorted(e.amount_qc for e in original_entries) == [-2_500, 2_500]

    ledger = (await client.get("/api/v1/admin/wallet/transactions")).json()["items"]
    assert ledger[0]["type"] == "REVERSAL" and ledger[1]["reversed"] is True
    recon = (await client.get("/api/v1/admin/wallet/reconcile")).json()
    assert recon["ok"] is True and recon["total_balance_qc"] == 0


async def test_reversal_cannot_overdraw(client, db, funded):
    async with atomic(db):
        await ws.pay_into_escrow(db, funded.buyer.id, 50_000, "o6:pay", memo="all in", meta={})
    welcome = await db.scalar(
        select(LedgerTransaction).where(
            LedgerTransaction.idempotency_key == f"welcome:{funded.buyer.id}"
        )
    )
    await login(client, "admin@queneth.test")
    res = await client.post(
        f"/api/v1/admin/wallet/transactions/{welcome.id}/reverse", json={"reason": "Clawback test"}
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "insufficient_funds"
    await assert_reconciled(db)


async def test_admin_codes_and_system_balances(client, funded):
    await login(client, "admin@queneth.test")
    created = await client.post(
        "/api/v1/admin/wallet/codes",
        json={"amount_qc": 2_000, "max_uses": 3, "code": "que launch 2026"},
    )
    assert created.status_code == 201 and created.json()["code"] == "QUE-LAUNCH-2026"
    dup = await client.post(
        "/api/v1/admin/wallet/codes", json={"amount_qc": 2_000, "code": "QUE-LAUNCH-2026"}
    )
    assert dup.status_code == 409
    generated = (await client.post("/api/v1/admin/wallet/codes", json={"amount_qc": 500})).json()
    assert generated["code"].startswith("QUE-")
    system = (await client.get("/api/v1/admin/wallet/system")).json()
    assert [s["code"] for s in system] == [
        "ISSUANCE",
        "ESCROW",
        "PLATFORM_REVENUE",
        "OUT_SIMULATED",
    ]
    assert system[0]["balance_qc"] == -100_000

    await login(client, "seller@queneth.test")
    assert (await client.get("/api/v1/admin/wallet/reconcile")).status_code == 403


# ─── Reconciliation catches tampering ──────────────────────────────────────


async def test_reconcile_reports_drift(db, funded):
    await assert_reconciled(db)
    wallet = await ws.user_wallet(db, funded.buyer.id)
    # Simulate a bug that changed a cached balance without a ledger entry.
    await db.execute(
        update(Wallet).where(Wallet.id == wallet.id).values(balance_qc=Wallet.balance_qc + 1)
    )
    await db.commit()
    report = await ws.reconcile(db)
    assert not report.ok
    assert len(report.drift) == 1 and report.drift[0].cached_qc - report.drift[0].computed_qc == 1
    assert report.total_balance_qc == 1


async def test_ledger_sum_is_zero_across_all_wallets(db, funded):
    total = await db.scalar(select(func.sum(LedgerEntry.amount_qc)))
    assert total == 0


async def test_post_keeps_unflushed_wallet_changes(db, accounts):
    """Regression: locking re-reads wallets; pending edits must survive it."""
    wallet = await ws.user_wallet(db, accounts.buyer.id)
    wallet.pin_hash = hash_password("123456")  # not flushed yet
    await ws.grant_welcome(db, accounts.buyer)
    fresh = await db.scalar(
        select(Wallet).where(Wallet.id == wallet.id).execution_options(populate_existing=True)
    )
    assert fresh.pin_hash is not None and fresh.balance_qc == ws.WELCOME_GRANT_QC
