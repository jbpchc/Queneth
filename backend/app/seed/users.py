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
