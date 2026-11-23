"""Seed the database.

    python -m app.seed          # base only: taxonomy, admin, system wallets
    python -m app.seed --demo   # plus the demo marketplace (7 boutiques, 124 pieces …)
    python -m app.seed --brands # plus Nike, Penshoppe and Bench with their pieces

Both are idempotent: re-running only adds what's missing.
"""

import asyncio
import sys

from app.db.session import SessionLocal, engine
from app.seed.base import seed_base
from app.seed.brand_sellers import seed_brand_sellers
from app.seed.demo import seed_demo


async def main(demo: bool, brands: bool = False) -> None:
    async with SessionLocal() as session:
        base = await seed_base(session)
        print(
            f"Base: {base['categories']} categories, admin {'created' if base['admins'] else 'present'}"
        )
        if demo:
            await seed_demo(session)
        else:
            print("No demo data (run with --demo to add the demo marketplace).")
        if brands:
            print("Brand sellers:", await seed_brand_sellers(session))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main("--demo" in sys.argv, "--brands" in sys.argv))
