"""Wallet seed: every demo shopper/seller gets a wallet funded *through the
ledger* (the same welcome grant real sign-ups get), so reconciliation passes
from day one. Demo PIN is 123456 (README). Idempotent."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password, utcnow
from app.models import TopUpCode, User
from app.services import wallet_service as ws

DEMO_PIN = "123456"  # documented in the README; demo-only

DEMO_CODES = [
    ("QUE-DEMO-5000", 5_000, 100, "Demo code for testers"),
    ("QUE-WELCOME-1000", 1_000, 500, "Thank-you code from the Queneth team"),
]


async def seed_wallets(session: AsyncSession) -> dict[str, int]:
    await ws.ensure_system_wallets(session)
    users = (await session.scalars(select(User).order_by(User.email))).all()
    pin_hash = hash_password(DEMO_PIN)
    funded = 0
    for user in users:
        if user.has_role(Role.ADMIN):
            continue  # admins operate the platform wallet; they don't shop
        wallet = await ws.user_wallet(session, user.id)
        if wallet.pin_hash is None:
            wallet.pin_hash = pin_hash
        before = wallet.balance_qc
        await ws.grant_welcome(session, user)
        funded += int(wallet.balance_qc != before)
    have = set((await session.scalars(select(TopUpCode.code))).all())
    admin = await session.scalar(select(User).where(User.email == "admin@queneth.test"))
    for code, amount, uses, memo in DEMO_CODES:
        if code not in have:
            session.add(
                TopUpCode(
                    code=code,
                    amount_qc=amount,
                    max_uses=uses,
                    memo=memo,
                    expires_at=utcnow() + timedelta(days=365),
                    created_by=admin.id if admin else None,
                )
            )
    await session.commit()
    return {"funded": funded}
