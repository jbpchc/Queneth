"""Promotions: admin campaigns, seller enrollment, sale prices applied and
restored, the public deals feed, and the clean (no demo) marketplace."""

import uuid
from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import utcnow
from app.models.catalog import Product, SellerProfile, Variant
from app.services import promotion_service as ps
from tests.test_checkout import login

A = "/api/v1/admin/promotions"
S = "/api/v1/seller/promotions"
SELLER = "nocturne@queneth.test"
OTHER_SELLER = "obra@queneth.test"
ADMIN = "admin@queneth.test"


def campaign(start_in: timedelta = timedelta(minutes=-5), **kw) -> dict:
    now = utcnow()
    body = {
        "title": "End of the Year Sale",
        "badge": "Year-End Sale",
        "description": "Our boutiques' last markdowns of the year.",
        "starts_at": (now + start_in).isoformat(),
        "ends_at": (now + start_in + timedelta(days=7)).isoformat(),
        "min_discount_percent": 10,
        "max_discount_percent": 50,
    }
    return body | kw


async def nocturne_products(db, n: int = 2) -> list[Product]:
    rows = await db.scalars(
        select(Product)
        .join(SellerProfile, SellerProfile.id == Product.seller_id)
        .where(SellerProfile.slug == "nocturne-parfums", Product.status == "active")
        .order_by(Product.slug)
        .limit(n)
    )
    return list(rows.all())


async def prices(db, product_id) -> list[tuple[int, int | None]]:
    rows = await db.scalars(
        select(Variant)
        .where(Variant.product_id == product_id)
        .order_by(Variant.id)
        .execution_options(populate_existing=True)
    )
    return [(v.price_qc, v.compare_at_qc) for v in rows.all()]


async def test_live_sale_applies_and_restores_prices(client, shop):
    db = shop
    await login(client, ADMIN)
    res = await client.post(A, json=campaign())
    assert res.status_code == 201, res.text
    promo = res.json()
    assert promo["state"] == "live" and promo["slug"] == "end-of-the-year-sale"

    p1, p2 = await nocturne_products(db)
    before = await prices(db, p1.id)

    await login(client, SELLER)
    res = await client.get(S)
    assert [o["id"] for o in res.json()["open"]] == [promo["id"]]
    # Outside the campaign's range is refused.
    res = await client.post(
        f"{S}/{promo['id']}/entries", json={"product_ids": [str(p1.id)], "discount_percent": 60}
    )
    assert res.status_code == 422 and res.json()["error"]["code"] == "discount_out_of_range"
    res = await client.post(
        f"{S}/{promo['id']}/entries",
        json={"product_ids": [str(p1.id), str(p2.id)], "discount_percent": 20},
    )
    assert res.status_code == 200, res.text
    entries = res.json()["entries"]
    assert {e["status"] for e in entries} == {"live"}

    after = await prices(db, p1.id)
    for (old, _), (new, was) in zip(before, after, strict=True):
        assert new == old * 80 // 100 and was == old

    # Shoppers see it on the deals feed and the campaign page.
    deals = (await client.get("/api/v1/catalog/deals")).json()
    assert deals["promotions"][0]["slug"] == promo["slug"]
    assert deals["promotions"][0]["top_discount_percent"] == 20
    assert {c["slug"] for c in deals["on_sale"]} >= {p1.slug, p2.slug}
    detail = (await client.get(f"/api/v1/catalog/promotions/{promo['slug']}")).json()
    assert len(detail["products"]) == 2

    # Prices are locked while the sale runs.
    product = (await client.get(f"/api/v1/seller/products/{p1.id}")).json()
    variants = [
        {k: v[k] for k in ("id", "options", "stock", "low_stock_threshold", "compare_at_qc")}
        | {"price_qc": v["price_qc"] + 100}
        for v in product["variants"]
    ]
    res = await client.patch(f"/api/v1/seller/products/{p1.id}", json={"variants": variants})
    assert res.status_code == 409 and res.json()["error"]["code"] == "price_locked_by_sale"

    # Withdrawing restores the original prices exactly.
    entry = next(e for e in entries if e["product_id"] == str(p1.id))
    assert (await client.delete(f"{S}/entries/{entry['id']}")).status_code == 204
    assert await prices(db, p1.id) == before

    # Cancelling the campaign restores the rest.
    p2_sale = await prices(db, p2.id)
    await login(client, ADMIN)
    assert (await client.post(f"{A}/{promo['id']}/cancel")).status_code == 204
    restored = await prices(db, p2.id)
    assert all(was is None or was > price for price, was in restored)
    assert [p for p, _ in restored] != [p for p, _ in p2_sale]
    assert (await client.get("/api/v1/catalog/deals")).json()["promotions"] == []


async def test_scheduled_sale_starts_and_ends_with_the_sweep(client, shop):
    db = shop
    await login(client, ADMIN)
    promo = (await client.post(A, json=campaign(timedelta(hours=1)))).json()
    assert promo["state"] == "upcoming"
    (p1,) = await nocturne_products(db, 1)
    before = await prices(db, p1.id)

    await login(client, SELLER)
    res = await client.post(
        f"{S}/{promo['id']}/entries", json={"product_ids": [str(p1.id)], "discount_percent": 10}
    )
    assert res.json()["entries"][0]["status"] == "scheduled"
    assert await prices(db, p1.id) == before  # nothing changes before the start
    assert (await client.get("/api/v1/catalog/deals")).json()["promotions"] == []

    # Admin moves the start into the past: the sweep starts the sale.
    await login(client, ADMIN)
    res = await client.put(f"{A}/{promo['id']}", json=campaign())
    assert res.json()["state"] == "live"
    assert [p for p, _ in await prices(db, p1.id)] == [old * 90 // 100 for old, _ in before]

    # And once the window has passed the sweep restores prices.
    from app.models.promotions import Promotion

    p = await db.get(Promotion, uuid.UUID(promo["id"]))
    p.starts_at, p.ends_at = utcnow() - timedelta(days=2), utcnow() - timedelta(minutes=1)
    await db.commit()
    assert (await ps.sweep(db))["restored"] == 1
    assert await prices(db, p1.id) == before


async def test_sellers_only_enroll_their_own_pieces(client, shop):
    db = shop
    await login(client, ADMIN)
    promo = (await client.post(A, json=campaign())).json()
    (p1,) = await nocturne_products(db, 1)
    await login(client, OTHER_SELLER)
    res = await client.post(
        f"{S}/{promo['id']}/entries", json={"product_ids": [str(p1.id)], "discount_percent": 20}
    )
    assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_products"
    # Shoppers can't run campaigns.
    await login(client, "buyer@queneth.test")
    assert (await client.post(A, json=campaign())).status_code == 403


async def test_no_stacking_across_overlapping_sales(client, shop):
    db = shop
    await login(client, ADMIN)
    first = (await client.post(A, json=campaign())).json()
    second = (await client.post(A, json=campaign(title="Holiday Edit", badge="Holiday"))).json()
    assert second["slug"] == "holiday-edit"
    (p1,) = await nocturne_products(db, 1)
    await login(client, SELLER)
    ok = await client.post(
        f"{S}/{first['id']}/entries", json={"product_ids": [str(p1.id)], "discount_percent": 20}
    )
    assert ok.status_code == 200
    res = await client.post(
        f"{S}/{second['id']}/entries", json={"product_ids": [str(p1.id)], "discount_percent": 20}
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "already_on_sale"


async def test_clean_marketplace_has_no_products(client, db):
    """The base seed alone: taxonomy and an admin, no boutiques, no pieces."""
    from app.seed.base import seed_base

    await seed_base(db)
    home = (await client.get("/api/v1/catalog/home")).json()
    assert home["curated"] == [] and home["featured_boutiques"] == []
    assert home["categories"] and all(c["cover_url"] is None for c in home["categories"])
    assert all(c["cover_images"] == [] for c in home["categories"])
    deals = (await client.get("/api/v1/catalog/deals")).json()
    assert deals == {"promotions": [], "on_sale": []}
    assert get_settings()  # settings import stays used for the app fixture
