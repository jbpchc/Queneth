"""Catalog: seed integrity, listings, facets, search, product pages, shopper actions."""

from functools import lru_cache

import pytest
from sqlalchemy import func, select

from app.core.permissions import Permission, can
from app.models import Drop, Product, Review, SellerProfile, User
from app.schemas.catalog_attributes import ClothingAttributes, validate_attributes
from app.seed import catalog as seed_catalog_mod
from app.seed import users as seed_users_mod
from app.seed.catalog import seed_catalog
from app.seed.users import seed_users
from tests.conftest import TEST_PASSWORD

P = "/api/v1/catalog"


@pytest.fixture
async def catalog(db, monkeypatch):
    # Argon2 is deliberately slow; hash the shared demo password once per run.
    from app.core import security

    cached = lru_cache(maxsize=4)(security.hash_password)
    monkeypatch.setattr(seed_users_mod, "hash_password", cached)
    monkeypatch.setattr(seed_catalog_mod, "hash_password", cached)
    await seed_users(db)
    await seed_catalog(db)
    return db


async def _login(client, email):
    client.cookies.clear()
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert res.status_code == 200, res.text


# ─── Seed ──────────────────────────────────────────────────────────────────


async def test_seed_is_complete_and_idempotent(catalog):
    db = catalog
    assert await db.scalar(select(func.count()).select_from(Product)) >= 120
    assert await db.scalar(select(func.count()).select_from(Review)) >= 40
    assert await db.scalar(select(func.count()).select_from(SellerProfile)) == 7
    assert await db.scalar(select(func.count()).select_from(Drop)) == 3
    again = await seed_catalog(db)
    assert again == {"products": 0, "reviews": 0}
    for p in (await db.scalars(select(Product))).all():
        assert len(p.images) >= 3, p.title
        assert all(img.alt for img in p.images)
        validate_attributes(
            p.category.slug, p.attributes
        )  # every product passes its category model


def test_clothing_composition_must_total_100():
    with pytest.raises(ValueError, match="100%"):
        ClothingAttributes(fit="slim", composition=[{"fiber": "silk", "pct": 90}])


async def test_seller_owns_only_their_products(catalog):
    db = catalog
    lumen = await db.scalar(select(User).where(User.email == "nocturne@queneth.test"))
    verde = await db.scalar(select(User).where(User.email == "verde@queneth.test"))
    product = await db.scalar(select(Product).where(Product.seller_id == lumen.seller_id))
    assert lumen.seller_id is not None
    assert can(lumen, Permission.PRODUCT_UPDATE, product)
    assert not can(verde, Permission.PRODUCT_UPDATE, product)


# ─── Home, categories, listings ────────────────────────────────────────────


async def test_home_feed(client, catalog):
    home = (await client.get(f"{P}/home")).json()
    assert home["live_drop"]["status"] == "live" and len(home["live_drop"]["products"]) == 3
    assert home["upcoming_drop"]["status"] == "upcoming"
    assert home["upcoming_drop"]["products"] == []  # no early peeks
    assert [c["slug"] for c in home["categories"]] == [
        "clothing",
        "shoes",
        "bags",
        "accessories",
        "perfumes",
    ]
    for rail in ("curated", "trending", "new_arrivals"):
        assert len(home[rail]) == 12
        assert all(card["total_stock"] > 0 for card in home[rail])
    assert home["featured_boutiques"] and home["editorial"]["product_count"] > 0
    card = home["curated"][0]
    assert card["image"]["url"].startswith("http") and card["hover_image"]


async def test_category_listing_and_disjunctive_facets(client, catalog):
    base = (await client.get(f"{P}/products", params={"category": "perfumes", "limit": 96})).json()
    assert {"notes", "concentration", "family"} <= set(base["facets"]["extra"])
    woody = next(f for f in base["facets"]["extra"]["family"] if f["value"] == "Woody")

    res = (
        await client.get(
            f"{P}/products", params={"category": "perfumes", "facet": "family:Woody", "limit": 96}
        )
    ).json()
    assert res["total"] == woody["count"]
    # The family facet still shows every family's count (disjunctive faceting).
    assert res["facets"]["extra"]["family"] == base["facets"]["extra"]["family"]
    detail = (await client.get(f"{P}/products/{res['items'][0]['slug']}")).json()
    assert detail["attributes"]["family"] == "Woody"


async def test_size_color_price_filters(client, catalog):
    res = (
        await client.get(
            f"{P}/products", params={"category": "clothing", "size": "XXS", "limit": 96}
        )
    ).json()
    assert res["total"] > 0 and all("XXS" in c["sizes"] for c in res["items"])
    res = (
        await client.get(f"{P}/products", params={"color": ["Noir", "Ivory"], "limit": 96})
    ).json()
    assert all({"Noir", "Ivory"} & {s["name"] for s in c["colors"]} for c in res["items"])
    res = (
        await client.get(
            f"{P}/products", params={"price_min": 5000, "price_max": 9000, "limit": 96}
        )
    ).json()
    assert res["total"] > 0 and all(5000 <= c["price_qc"] <= 9000 for c in res["items"])


async def test_sorts_and_sold_out_last(client, catalog):
    res = (await client.get(f"{P}/products", params={"sort": "price_asc", "limit": 96})).json()
    available = [c["price_qc"] for c in res["items"] if c["total_stock"] > 0]
    assert available == sorted(available)
    stock = [c["total_stock"] > 0 for c in res["items"]]
    assert stock == sorted(stock, reverse=True)  # sold-out pieces sink to the end
    res = (
        await client.get(f"{P}/products", params={"sort": "price_desc", "category": "bags"})
    ).json()
    prices = [c["price_qc"] for c in res["items"] if c["total_stock"] > 0]
    assert prices == sorted(prices, reverse=True)


async def test_cursor_pagination_covers_everything_once(client, catalog):
    seen: list[str] = []
    cursor, total = None, None
    while True:
        params = {"limit": 24, **({"cursor": cursor} if cursor else {})}
        page = (await client.get(f"{P}/products", params=params)).json()
        total = page["total"]
        seen += [c["id"] for c in page["items"]]
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
    assert len(seen) == total == len(set(seen))


async def test_bad_cursor_is_422(client, catalog):
    res = await client.get(f"{P}/products", params={"cursor": "garbage!!"})
    assert res.status_code == 422


async def test_connoisseur_pick_is_highlighted(client, catalog):
    res = (await client.get(f"{P}/products", params={"category": "shoes"})).json()
    pick = res["connoisseur_pick_id"]
    assert pick and any(c["id"] == pick and "connoisseur_pick" in c["badges"] for c in res["items"])


# ─── Search ────────────────────────────────────────────────────────────────


async def test_search_exact_typo_and_accents(client, catalog):
    res = await client.get(f"{P}/products", params={"q": "figue"})
    assert res.json()["items"][0]["title"] == "Figue Noire"

    typo = await client.get(f"{P}/products", params={"q": "bergamt"})
    assert typo.json()["total"] > 0
    assert typo.headers["X-Search-Corrected"] == "bergamot"

    accents = (await client.get(f"{P}/products", params={"q": "neroli lumiere"})).json()
    assert accents["items"][0]["title"] == "Néroli Lumière"

    none = (await client.get(f"{P}/products", params={"q": "zzqxv"})).json()
    assert none["total"] == 0 and none["items"] == []


async def test_suggest(client, catalog):
    s = (await client.get(f"{P}/suggest", params={"q": "obra"})).json()
    assert any(b["slug"] == "obra-leather" for b in s["boutiques"])
    assert any(b["name"] == "Obra" for b in s["brands"])
    assert (await client.get(f"{P}/suggest", params={"q": "a"})).status_code == 422


async def test_scheduled_drop_products_are_hidden(client, catalog, db):
    drop = await db.scalar(select(Drop).where(Drop.slug == "kintsugi-gold"))
    hidden = drop.products[0]
    listing = (
        await client.get(f"{P}/products", params={"limit": 96, "category": "accessories"})
    ).json()
    assert hidden.slug not in {c["slug"] for c in listing["items"]}
    assert (await client.get(f"{P}/products/{hidden.slug}")).status_code == 404


# ─── Product page ──────────────────────────────────────────────────────────


async def test_perfume_page(client, catalog):
    page = (await client.get(f"{P}/products/{(await _slug(client, 'Figue Noire'))}")).json()
    assert page["variant_axes"] == ["volume"]
    assert [v["options"]["volume"] for v in page["variants"]] == ["30 ml", "50 ml", "100 ml"]
    assert page["attributes"]["top_notes"] and 1 <= page["attributes"]["sillage"] <= 5
    assert page["similar_scents"] and all(
        c["category"] == "perfumes" for c in page["similar_scents"]
    )
    assert page["review_summary"]["fit"] is None


async def test_clothing_page_rails_and_reviews(client, catalog):
    res = (
        await client.get(f"{P}/products", params={"category": "clothing", "sort": "most_wished"})
    ).json()
    page = (await client.get(f"{P}/products/{res['items'][0]['slug']}")).json()
    assert page["variant_axes"] == ["size", "color"]
    assert page["complete_the_look"] and all(
        c["category"] != "clothing" for c in page["complete_the_look"]
    )
    assert all(c["category"] == "clothing" for c in page["you_may_also_love"])
    assert page["similar_scents"] == []
    s = page["review_summary"]
    assert s["count"] == sum(s["distribution"].values())
    if s["count"]:
        assert s["fit"] and sum(s["fit"].values()) in (99, 100, 101)
        assert page["reviews"][0]["author"].endswith(".")  # "Ana S." — surnames abbreviated


async def test_reviews_pagination(client, catalog, db):
    slug = await db.scalar(select(Product.slug).where(Product.rating_count >= 2))
    first = (await client.get(f"{P}/products/{slug}/reviews", params={"limit": 1})).json()
    assert len(first["items"]) == 1 and first["has_more"]
    second = (
        await client.get(
            f"{P}/products/{slug}/reviews", params={"limit": 1, "cursor": first["next_cursor"]}
        )
    ).json()
    assert second["items"][0]["id"] != first["items"][0]["id"]


async def _slug(client, title: str) -> str:
    res = (await client.get(f"{P}/products", params={"q": title})).json()
    return next(c["slug"] for c in res["items"] if c["title"] == title)


# ─── Boutiques, collections, drops ─────────────────────────────────────────


async def test_boutiques_and_follow(client, catalog):
    listing = (await client.get(f"{P}/boutiques")).json()
    assert len(listing) == 7 and all(b["product_count"] > 0 for b in listing)
    before = (await client.get(f"{P}/boutiques/obra-leather")).json()
    assert before["bio"] and before["rating_count"] >= 0

    assert (await client.put(f"{P}/boutiques/obra-leather/follow")).status_code == 401
    await _login(client, "buyer@queneth.test")
    on = (await client.put(f"{P}/boutiques/obra-leather/follow")).json()
    assert on == {"is_following": True, "follower_count": before["follower_count"] + 1}
    again = (await client.put(f"{P}/boutiques/obra-leather/follow")).json()
    assert again["follower_count"] == before["follower_count"] + 1  # idempotent
    assert (await client.get(f"{P}/boutiques/obra-leather")).json()["is_following"] is True
    off = (await client.delete(f"{P}/boutiques/obra-leather/follow")).json()
    assert off["follower_count"] == before["follower_count"]

    await _login(client, "obra@queneth.test")
    assert (await client.put(f"{P}/boutiques/obra-leather/follow")).status_code == 409


async def test_collections(client, catalog):
    cols = (await client.get(f"{P}/collections")).json()
    assert [c["slug"] for c in cols] == ["the-quiet-luxury-edit", "citrus-and-sun", "after-hours"]
    tag = cols[0]["tag"]
    listing = (await client.get(f"{P}/products", params={"tag": tag, "limit": 96})).json()
    assert listing["total"] == cols[0]["product_count"] > 0


async def test_drop_notify(client, catalog):
    await _login(client, "buyer@queneth.test")
    on = await client.put(f"{P}/drops/kintsugi-gold/notify")
    assert on.json() == {"is_subscribed": True}
    drops = (await client.get(f"{P}/drops")).json()
    assert next(d for d in drops if d["slug"] == "kintsugi-gold")["is_subscribed"] is True
    assert (await client.put(f"{P}/drops/night-garden/notify")).status_code == 409  # already live


# ─── Wishlist & bag ────────────────────────────────────────────────────────


async def _first_in_stock(client, **params):
    res = (await client.get(f"{P}/products", params={"limit": 96, **params})).json()
    card = next(c for c in res["items"] if c["total_stock"] > 0)
    return (await client.get(f"{P}/products/{card['slug']}")).json()


async def test_wishlist(client, catalog):
    page = await _first_in_stock(client)
    pid = page["id"]
    assert (await client.put(f"/api/v1/wishlist/{pid}")).status_code == 401
    await _login(client, "buyer@queneth.test")
    first = (await client.put(f"/api/v1/wishlist/{pid}")).json()
    second = (await client.put(f"/api/v1/wishlist/{pid}")).json()
    assert first["saved"] and first["wishlist_count"] == second["wishlist_count"]
    assert (await client.get("/api/v1/wishlist/ids")).json() == {"product_ids": [pid]}
    wl = (await client.get("/api/v1/wishlist")).json()
    assert wl["count"] == 1 and wl["items"][0]["product"]["id"] == pid
    assert (await client.delete(f"/api/v1/wishlist/{pid}")).status_code == 204
    assert (await client.get("/api/v1/wishlist/ids")).json() == {"product_ids": []}

    await _login(client, "admin@queneth.test")
    assert (await client.put(f"/api/v1/wishlist/{pid}")).status_code == 403  # admins don't shop


async def _variant_with_stock(client, minimum: int, **params):
    res = (await client.get(f"{P}/products", params={"limit": 96, **params})).json()
    for card in res["items"]:
        page = (await client.get(f"{P}/products/{card['slug']}")).json()
        for v in page["variants"]:
            if v["stock"] >= minimum:
                return v
    raise AssertionError("seed has no variant with enough stock")


async def test_bag_flow(client, catalog):
    variant = await _variant_with_stock(client, 3, category="perfumes")
    await _login(client, "buyer@queneth.test")
    bag = (
        await client.post("/api/v1/cart/items", json={"variant_id": variant["id"], "qty": 1})
    ).json()
    assert bag["item_count"] == 1 and bag["subtotal_qc"] == variant["price_qc"]
    bag = (
        await client.post("/api/v1/cart/items", json={"variant_id": variant["id"], "qty": 1})
    ).json()
    assert bag["item_count"] == 2 and len(bag["groups"]) == 1  # merged, grouped by boutique

    too_many = await client.post(
        "/api/v1/cart/items", json={"variant_id": variant["id"], "qty": variant["stock"]}
    )
    assert too_many.status_code == 409 and too_many.json()["error"]["code"] == "insufficient_stock"

    item_id = bag["groups"][0]["items"][0]["id"]
    bag = (await client.patch(f"/api/v1/cart/items/{item_id}", json={"qty": 1})).json()
    assert bag["item_count"] == 1

    await _login(client, "collector@queneth.test")  # someone else's bag item looks missing
    assert (await client.patch(f"/api/v1/cart/items/{item_id}", json={"qty": 1})).status_code == 404

    await _login(client, "buyer@queneth.test")
    bag = (await client.delete(f"/api/v1/cart/items/{item_id}")).json()
    assert bag["item_count"] == 0 and bag["groups"] == []


async def test_seller_cannot_bag_own_product(client, catalog, db):
    page = await _first_in_stock(client, boutique="obra-leather")
    variant = next(v for v in page["variants"] if v["stock"] > 0)
    await _login(client, "obra@queneth.test")
    res = await client.post("/api/v1/cart/items", json={"variant_id": variant["id"]})
    assert res.status_code == 409 and res.json()["error"]["code"] == "own_product"


# ─── Generated art ─────────────────────────────────────────────────────────


async def test_art_endpoint(client):
    res = await client.get(f"{P}/art/p/dress/1.svg", params={"c": "b08457", "m": "AL"})
    assert res.status_code == 200 and res.headers["content-type"].startswith("image/svg+xml")
    assert "immutable" in res.headers["cache-control"] and res.text.startswith("<svg")
    assert (
        await client.get(f"{P}/art/p/spaceship/1.svg", params={"c": "b08457"})
    ).status_code == 404
    assert (await client.get(f"{P}/art/p/dress/1.svg", params={"c": "red"})).status_code == 422
    assert (await client.get(f"{P}/art/p/dress/9.svg", params={"c": "b08457"})).status_code == 422


async def test_seed_photos_keep_svg_fallback_and_primary_swatch(client, catalog):
    from app.seed.photos import apply_photos

    db = catalog
    first = await apply_photos(db)
    assert first["products"] > 100 and first["banners"] == 7 and first["heroes"] >= 3
    again = await apply_photos(db)
    assert again == {"products": 0, "banners": 0, "heroes": 0}  # idempotent

    product = await db.scalar(
        select(Product).where(Product.status == "active").order_by(Product.slug).limit(1)
    )
    page = (await client.get(f"{P}/products/{product.slug}")).json()
    urls = [i["url"] for i in page["images"]]
    assert urls[0].startswith("https://images.unsplash.com/photo-")
    assert "fb=%2Fapi%2Fv1%2Fcatalog%2Fart%2F" in urls[0]  # SVG fallback travels with it
    # The primary color keeps a color-correct (SVG) shot for its swatch.
    primary = page["images"][len([u for u in urls if "unsplash" in u])]
    assert "/catalog/art/" in primary["url"] and primary["color"]
    cats = (await client.get(f"{P}/categories")).json()
    assert cats and all(c["cover_url"].startswith("https://images.unsplash.com/") for c in cats)
