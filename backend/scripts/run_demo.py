"""Run the Queneth API without Docker or Postgres, on a local SQLite file.

    cd backend
    .venv/Scripts/python scripts/run_demo.py           # a clean marketplace, data kept between runs
    .venv/Scripts/python scripts/run_demo.py --demo    # also load the demo boutiques and products
    .venv/Scripts/python scripts/run_demo.py --brands  # also add Nike, Penshoppe and Bench
    .venv/Scripts/python scripts/run_demo.py --reset   # delete everything and start over
    .venv/Scripts/python scripts/run_demo.py --public  # reachable from outside a VM

Data lives in backend/demo.db (git-ignored); scripts/snapshot.py copies it,
with its photos, to another computer. Seeding only adds what's missing,
so the boutiques, products and orders you create in the app are kept.
For the full stack (Postgres) use `docker compose up`.
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "demo.db"

if "--reset" in sys.argv and DB.exists():
    DB.unlink()
    print("Reset: removed demo.db")

# Must be set before the app's settings and engine are imported.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB.as_posix()}"
sys.path.insert(0, str(BACKEND))

import uvicorn  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import Base  # noqa: E402
from app.seed.base import seed_base  # noqa: E402
from app.seed.brand_sellers import seed_brand_sellers  # noqa: E402
from app.seed.demo import seed_demo  # noqa: E402


async def prepare() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # no-op for existing tables
    async with SessionLocal() as s:
        print("base:", await seed_base(s))
        if "--demo" in sys.argv:
            await seed_demo(s)
        if "--brands" in sys.argv:
            print("brand sellers:", await seed_brand_sellers(s))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(prepare())
    print(f"Database: {DB}")
    host = "0.0.0.0" if "--public" in sys.argv else "127.0.0.1"
    uvicorn.run("app.main:app", host=host, port=8000)
