"""The demo marketplace (opt-in): made-up boutiques, products, reviews,
wallets, vouchers, addresses and an order history. Used by `--demo` and tests."""


async def seed_demo(session) -> None:  # type: ignore[no-untyped-def]
    """The demo marketplace: made-up boutiques, products, reviews, wallets,
    vouchers, addresses and an order history. For demos and tests only."""
    from app.seed.catalog import seed_catalog
    from app.seed.commerce import seed_commerce
    from app.seed.orders import seed_orders
    from app.seed.photos import apply_photos
    from app.seed.users import seed_users
    from app.seed.wallet import seed_wallets

    created = await seed_users(session)
    print(f"Demo users: {len(created)} created" + (f" ({', '.join(created)})" if created else ""))
    catalog = await seed_catalog(session)
    print(f"Demo catalog: {catalog['products']} products, {catalog['reviews']} reviews")
    photos = await apply_photos(session)
    print(f"Demo photos: {photos['products']} products, {photos['banners']} banners")
    wallets = await seed_wallets(session)
    print(f"Demo wallets: {wallets['funded']} funded; demo PIN 123456")
    commerce = await seed_commerce(session)
    print(f"Demo commerce: {commerce['vouchers']} vouchers, {commerce['addresses']} addresses")
    print(f"Demo orders: {await seed_orders(session)}")
