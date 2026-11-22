import asyncio

from app.db.session import SessionLocal, engine
from app.seed.catalog import seed_catalog
from app.seed.commerce import seed_commerce
from app.seed.orders import seed_orders
from app.seed.photos import apply_photos
from app.seed.users import seed_users
from app.seed.wallet import seed_wallets


async def main() -> None:
    async with SessionLocal() as session:
        created = await seed_users(session)
        print(
            f"Users: {len(created)} created"
            + (f" ({', '.join(created)})" if created else " (all present)")
        )
        catalog = await seed_catalog(session)
        if catalog["products"]:
            print(
                f"Catalog: {catalog['products']} products, {catalog['reviews']} reviews, 3 collections, 3 drops"
            )
        else:
            print("Catalog: already seeded (nothing to do)")
        photos = await apply_photos(session)
        print(
            f"Photos: {photos['products']} products, {photos['banners']} banners, "
            f"{photos['heroes']} collection/drop heroes (Unsplash, SVG fallback)"
        )
        wallets = await seed_wallets(session)
        print(f"Wallets: {wallets['funded']} funded with the welcome grant; demo PIN 123456")
        commerce = await seed_commerce(session)
        print(f"Commerce: {commerce['vouchers']} vouchers, {commerce['addresses']} addresses")
        orders = await seed_orders(session)
        print(f"Orders: {orders} for collector@queneth.test (one in every status)")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
