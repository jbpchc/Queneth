"""Base seed: what a brand-new marketplace needs and nothing more.

- the platform taxonomy (5 categories and their subcategories, managed by
  admins in the Control Room afterwards);
- the admin account (admins are seeded, never self-registered);
- the QueWallet system wallets.

No boutiques, products, reviews, vouchers or orders: with no sellers the shop
shows zero items. The demo marketplace is opt-in (`python -m app.seed --demo`).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password, utcnow
from app.models.user import User
from app.seed.catalog import seed_taxonomy
from app.seed.users import DEMO_PASSWORD, DEMO_USERS
from app.services import wallet_service as ws


async def seed_base(session: AsyncSession) -> dict[str, int]:
    categories = await seed_taxonomy(session)
    admin = next(u for u in DEMO_USERS if Role.ADMIN in u.roles)
    created = 0
    if not await session.scalar(select(User.id).where(User.email == admin.email)):
        session.add(
            User(
                email=admin.email,
                name=admin.name,
                password_hash=hash_password(DEMO_PASSWORD),
                roles=[Role.ADMIN.value],
                email_verified_at=utcnow(),
            )
        )
        created = 1
    await ws.ensure_system_wallets(session)
    await session.commit()
    return {"categories": len(categories), "admins": created}
