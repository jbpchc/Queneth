"""Demo accounts (README). Re-running updates nothing that already exists."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password, utcnow
from app.models.user import User

DEMO_PASSWORD = "Queneth#2026"  # documented in the README; demo-only


@dataclass(frozen=True)
class DemoUser:
    email: str
    name: str
    roles: tuple[Role, ...]


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser("buyer@queneth.test", "Isabela Reyes", (Role.BUYER,)),
    DemoUser("collector@queneth.test", "Marco Villanueva", (Role.BUYER,)),
    # ADMIN is seeded only, never self-registered.
    DemoUser("admin@queneth.test", "Queneth Control Room", (Role.ADMIN,)),
)


async def seed_users(session: AsyncSession) -> list[str]:
    created: list[str] = []
    for demo in DEMO_USERS:
        exists = await session.scalar(select(User.id).where(User.email == demo.email))
        if exists:
            continue
        session.add(
            User(
                email=demo.email,
                name=demo.name,
                password_hash=hash_password(DEMO_PASSWORD),
                roles=[r.value for r in demo.roles],
                email_verified_at=utcnow(),
            )
        )
        created.append(demo.email)
    await session.commit()
    return created


async def seed_demo_buyers(session: AsyncSession) -> list[str]:
    """The README's shopper accounts (buyer@, collector@), ready to buy: each gets
    the welcome credit and the demo PIN. Brand stores are seller-only accounts,
    so a store seeded without the full demo still has buyers to shop with."""
    from app.seed.wallet import DEMO_PIN
    from app.services import wallet_service as ws

    await ws.ensure_system_wallets(session)
    created: list[str] = []
    for demo in DEMO_USERS:
        if demo.roles != (Role.BUYER,):
            continue
        user = await session.scalar(select(User).where(User.email == demo.email))
        if user is None:
            user = User(
                email=demo.email,
                name=demo.name,
                password_hash=hash_password(DEMO_PASSWORD),
                roles=[Role.BUYER.value],
                email_verified_at=utcnow(),
                seller_profile=None,
            )
            session.add(user)
            await session.flush()
            created.append(demo.email)
        wallet = await ws.user_wallet(session, user.id)
        if wallet.pin_hash is None:
            wallet.pin_hash = hash_password(DEMO_PIN)
        await ws.grant_welcome(session, user)
    await session.commit()
    return created
