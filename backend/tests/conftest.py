"""Shared fixtures.

Database: tests run against TEST_DATABASE_URL (a dedicated Postgres database,
never the dev one) when it is reachable. Otherwise they fall back to an
in-memory SQLite database so the suite still runs on a laptop without Docker.
Postgres-only behaviour (row locks, concurrency) is marked `@pytest.mark.postgres`
and skipped on the fallback.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("INTEGRATIONS_MODE", "mock")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.v1.routers.health import get_db_pinger  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.permissions import Role  # noqa: E402
from app.core.security import CSRF_COOKIE, CSRF_HEADER, hash_password  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, User  # noqa: E402

TEST_PASSWORD = "Queneth#2026"


async def _postgres_engine() -> AsyncEngine | None:
    url = get_settings().test_database_url
    if not url:
        return None
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with asyncio.timeout(2), engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        return engine
    except Exception:  # noqa: BLE001
        await engine.dispose()
        return None


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = await _postgres_engine()
    if eng is None:
        eng = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="session")
def is_postgres(engine: AsyncEngine) -> bool:
    return engine.dialect.name == "postgresql"


@pytest.fixture(autouse=True)
def _skip_postgres_only(request: pytest.FixtureRequest) -> None:
    needs_pg = request.node.get_closest_marker("postgres")
    if needs_pg and not request.getfixturevalue("is_postgres"):
        pytest.skip("needs Postgres (set TEST_DATABASE_URL)")


@pytest.fixture
async def session_factory(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    # Clean slate per test: truncate in reverse dependency order.
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def db(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture
def app(session_factory: async_sessionmaker[AsyncSession]):
    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def db_up() -> bool:
        return True

    async def pinger():
        return db_up

    application.state.session_factory = session_factory
    application.dependency_overrides[get_session] = override_session
    application.dependency_overrides[get_db_pinger] = pinger
    return application


def _attach_csrf(client: AsyncClient) -> None:
    """Mimic the frontend: echo the readable CSRF cookie in the header."""

    async def hook(request):  # type: ignore[no-untyped-def]
        token = client.cookies.get(CSRF_COOKIE)
        if token and request.method not in {"GET", "HEAD", "OPTIONS"}:
            request.headers[CSRF_HEADER] = token

    client.event_hooks["request"].append(hook)


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    """A browser-like client: keeps cookies and sends the CSRF header."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        _attach_csrf(ac)
        yield ac


@pytest.fixture
async def raw_client(app) -> AsyncIterator[AsyncClient]:
    """Keeps cookies but never sends the CSRF header (for CSRF tests)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@dataclass
class Accounts:
    buyer: User
    seller: User
    other_seller: User
    admin: User


@pytest.fixture
async def accounts(db: AsyncSession) -> Accounts:
    pw = hash_password(TEST_PASSWORD)

    def make(email: str, name: str, *roles: Role) -> User:
        return User(email=email, name=name, password_hash=pw, roles=[r.value for r in roles])

    users = Accounts(
        buyer=make("buyer@queneth.test", "Isabela Reyes", Role.BUYER),
        seller=make("seller@queneth.test", "Atelier Lumen", Role.BUYER, Role.SELLER),
        other_seller=make("seller2@queneth.test", "Maison Verde", Role.BUYER, Role.SELLER),
        admin=make("admin@queneth.test", "Control Room", Role.ADMIN),
    )
    db.add_all([users.buyer, users.seller, users.other_seller, users.admin])
    await db.commit()
    return users


@pytest.fixture
def login(client: AsyncClient) -> Callable[[str], object]:
    async def _login(email: str, password: str = TEST_PASSWORD) -> AsyncClient:
        client.cookies.clear()
        res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, res.text
        return client

    return _login


@pytest.fixture
async def shop(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> AsyncSession:
    """Full demo seed: users, catalog, wallets (PIN 123456), vouchers, addresses."""
    from functools import lru_cache

    from app.core import security
    from app.seed import catalog as seed_catalog_mod
    from app.seed import users as seed_users_mod
    from app.seed import wallet as seed_wallet_mod
    from app.seed.catalog import seed_catalog
    from app.seed.commerce import seed_commerce
    from app.seed.users import seed_users
    from app.seed.wallet import seed_wallets

    # Argon2 is deliberately slow; hash the shared demo password once per run.
    cached = lru_cache(maxsize=4)(security.hash_password)
    for mod in (seed_users_mod, seed_catalog_mod, seed_wallet_mod):
        monkeypatch.setattr(mod, "hash_password", cached)
    await seed_users(db)
    await seed_catalog(db)
    await seed_wallets(db)
    await seed_commerce(db)
    return db
