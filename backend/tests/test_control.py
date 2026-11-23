"""Phase 9: Admin Control Room — overview, seller directory & suspension, user
search, catalog editing, featured slots, reports and moderation, and that only
admins (with the right permission) get in."""

import uuid

from sqlalchemy import func, select

from app.models import User
from app.models.catalog import Product, Review, SellerProfile
from app.models.integration import ContentFlag, Notification
from app.models.user import AuditLog
from tests.test_checkout import add, default_address, login, pay, variant_from

A = "/api/v1/admin"
ADMIN = "admin@queneth.test"
BUYER = "buyer@queneth.test"
OTHER = "collector@queneth.test"
SELLER = "nocturne@queneth.test"


async def audited(db, action: str) -> int:
    return await db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == action)
    )


async def test_only_admins_get_in(client, shop):
    for email in (BUYER, SELLER):
        await login(client, email)
        for path in ("/overview", "/sellers", "/users", "/catalog/categories", "/moderation"):
            assert (await client.get(f"{A}{path}")).status_code == 403, path


async def test_overview_counts_real_sales(client, shop):
    await login(client, BUYER)
    bag = await add(client, await variant_from(shop, "obra-leather"))
    await pay(client, total=bag["total_qc"], address=await default_address(client))
    await login(client, ADMIN)
    o = (await client.get(f"{A}/overview")).json()
    assert o["gmv_qc"] == bag["total_qc"] and o["orders"] == 1 and o["orders_30d"] == 1
    assert o["escrow_qc"] == bag["total_qc"] and o["active_buyers_30d"] == 1
    assert o["sellers_active"] == 7 and len(o["series"]) == 30
    assert o["series"][-1]["revenue_qc"] == bag["total_qc"]
    assert o["top_categories"][0]["revenue_qc"] == bag["total_qc"]


async def test_seller_directory_suspend_and_reinstate(client, shop):
    await login(client, ADMIN)
    page = (await client.get(f"{A}/sellers")).json()
    assert page["counts"]["approved"] == 7
    obra = next(s for s in page["items"] if s["slug"] == "obra-leather")
    assert obra["owner"]["email"] == "obra@queneth.test" and obra["product_count"] > 0
    found = (await client.get(f"{A}/sellers", params={"q": "OBRA"})).json()["items"]
    assert [s["slug"] for s in found] == ["obra-leather"]

    no_reason = await client.post(f"{A}/sellers/{obra['id']}/suspend", json={"reason": ""})
    assert no_reason.status_code == 422
    res = await client.post(
        f"{A}/sellers/{obra['id']}/suspend", json={"reason": "Counterfeit reports under review"}
    )
    assert res.status_code == 204
    # Hidden from shoppers; Studio closed.
    assert (await client.get("/api/v1/catalog/boutiques/obra-leather")).status_code == 404
    await login(client, "obra@queneth.test")
    assert (await client.get("/api/v1/seller/dashboard")).status_code == 403
    owner = await shop.scalar(select(User).where(User.email == "obra@queneth.test"))
    assert (
        await shop.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == owner.id, Notification.type == "seller.status")
        )
        == 1
    )

    await login(client, ADMIN)
    assert (await client.post(f"{A}/sellers/{obra['id']}/reinstate")).status_code == 204
    assert (await client.get("/api/v1/catalog/boutiques/obra-leather")).status_code == 200
    assert (
        await audited(shop, "seller.suspend") == 1 and await audited(shop, "seller.reinstate") == 1
    )


async def test_user_search_and_detail(client, shop):
    await login(client, ADMIN)
    res = (await client.get(f"{A}/users", params={"q": "queneth.test", "role": "SELLER"})).json()
    assert res["total"] == 7 and all("SELLER" in u["roles"] for u in res["items"])
    lumen = next(u for u in res["items"] if u["email"] == SELLER)
    assert lumen["boutique"]["slug"] == "nocturne-parfums" and lumen["wallet_qc"] == 50_000
    page = (await client.get(f"{A}/users", params={"limit": 2, "offset": 0})).json()
    assert len(page["items"]) == 2 and page["total"] > 2
    detail = (await client.get(f"{A}/users/{lumen['id']}")).json()
    assert detail["email"] == SELLER and "recent_audit" in detail
    assert (await client.get(f"{A}/users/{uuid.uuid4()}")).status_code == 404


async def test_catalog_editing(client, shop):
    await login(client, ADMIN)
    cats = (await client.get(f"{A}/catalog/categories")).json()
    perfumes = next(c for c in cats if c["slug"] == "perfumes")
    assert perfumes["attribute_schema"] and perfumes["product_count"] > 0
    res = await client.patch(
        f"{A}/catalog/categories/{perfumes['id']}", json={"tagline": "Notes and memory."}
    )
    assert res.status_code == 204

    created = await client.post(
        f"{A}/catalog/categories/{perfumes['id']}/subcategories", json={"name": " Solid  perfume "}
    )
    assert created.status_code == 201
    dup = await client.post(
        f"{A}/catalog/categories/{perfumes['id']}/subcategories", json={"name": "Solid perfume"}
    )
    assert dup.status_code == 409
    cats = (await client.get(f"{A}/catalog/categories")).json()
    solid = next(s for c in cats for s in c["subcategories"] if s["slug"] == "solid-perfume")
    assert (
        await client.patch(
            f"{A}/catalog/subcategories/{solid['id']}", json={"name": "Solid perfumes"}
        )
    ).status_code == 204
    assert (await client.delete(f"{A}/catalog/subcategories/{solid['id']}")).status_code == 204
    busy = next(s for s in perfumes["subcategories"] if s["product_count"] > 0)
    res = await client.delete(f"{A}/catalog/subcategories/{busy['id']}")
    assert res.status_code == 409 and res.json()["error"]["code"] == "subcategory_in_use"
    # Sellers immediately see the edited taxonomy in the wizard.
    await login(client, SELLER)
    meta = (await client.get("/api/v1/seller/products/meta")).json()
    assert any(c["slug"] == "perfumes" for c in meta["categories"])


async def test_connoisseur_pick_is_one_per_subcategory(client, shop):
    await login(client, ADMIN)
    cats = (await client.get(f"{A}/catalog/categories")).json()
    sub = next(s for c in cats for s in c["subcategories"] if s["product_count"] >= 2)
    rows = (await client.get(f"{A}/catalog/subcategories/{sub['id']}/picks")).json()
    target = next(r for r in rows if not r["is_pick"])
    assert (
        await client.put(f"{A}/catalog/products/{target['id']}/pick", json={"on": True})
    ).status_code == 204
    rows = (await client.get(f"{A}/catalog/subcategories/{sub['id']}/picks")).json()
    assert [r["id"] for r in rows if r["is_pick"]] == [target["id"]]


async def test_collections_and_featured_boutiques(client, shop):
    await login(client, ADMIN)
    data = (await client.get(f"{A}/catalog/collections")).json()
    assert data["items"] and data["tags"]
    tag = data["tags"][0]["tag"]
    created = (
        await client.post(
            f"{A}/catalog/collections",
            json={
                "title": "Rainy Season Edit",
                "tag": tag.upper(),
                "kicker": "Edit",
                "is_featured": True,
            },
        )
    ).json()
    assert created["slug"] == "rainy-season-edit" and created["tag"] == tag
    assert (await client.get(f"/api/v1/catalog/collections/{created['slug']}")).status_code == 200
    upd = await client.put(
        f"{A}/catalog/collections/{created['id']}", json={"title": "Rainy Season", "tag": tag}
    )
    assert upd.json()["title"] == "Rainy Season"
    assert (await client.delete(f"{A}/catalog/collections/{created['id']}")).status_code == 204

    sellers = (await client.get(f"{A}/sellers")).json()["items"]
    target = next(s for s in sellers if not s["is_featured"])
    assert (
        await client.put(f"{A}/sellers/{target['id']}/featured", json={"on": True})
    ).status_code == 204
    profile = await shop.scalar(
        select(SellerProfile)
        .where(SellerProfile.id == uuid.UUID(target["id"]))
        .execution_options(populate_existing=True)
    )
    assert profile.is_featured is True


async def test_reports_and_moderation(client, shop):
    v = await variant_from(shop, "obra-leather")
    product = await shop.scalar(select(Product).where(Product.id == v.product_id))
    review = await shop.scalar(select(Review).where(Review.status == "published").limit(1))

    # Two shoppers report the same product; a repeat report is absorbed.
    for email in (BUYER, OTHER):
        await login(client, email)
        body = {
            "target_type": "product",
            "target_id": str(product.id),
            "reason": "counterfeit",
            "note": "Logo looks off",
        }
        assert (await client.post("/api/v1/reports", json=body)).status_code == 202
        assert (await client.post("/api/v1/reports", json=body)).status_code == 202
    assert await shop.scalar(select(func.count()).select_from(ContentFlag)) == 2
    bad = await client.post(
        "/api/v1/reports",
        json={"target_type": "product", "target_id": str(uuid.uuid4()), "reason": "spam"},
    )
    assert bad.status_code == 404
    reviewer = await shop.scalar(select(User).where(User.id == review.buyer_id))
    if reviewer.email != OTHER:
        await client.post(
            "/api/v1/reports",
            json={"target_type": "review", "target_id": str(review.id), "reason": "offensive"},
        )

    await login(client, ADMIN)
    queue = (await client.get(f"{A}/moderation")).json()
    top = queue[0]
    assert top["target_id"] == str(product.id) and top["reports"] == 2
    assert top["reasons"] == {"counterfeit": 2} and top["notes"] == [
        "Logo looks off",
        "Logo looks off",
    ]
    assert (await client.get(f"{A}/overview")).json()["open_reports"] == len(queue)

    # Take the product down: hidden from shoppers, seller told, Studio can't republish.
    res = await client.post(
        f"{A}/moderation/product/{product.id}", json={"action": "remove", "note": "Counterfeit"}
    )
    assert res.status_code == 204
    assert (await client.get(f"/api/v1/catalog/products/{product.slug}")).status_code == 404
    seller = await shop.scalar(select(SellerProfile).where(SellerProfile.id == product.seller_id))
    owner = await shop.scalar(select(User).where(User.id == seller.user_id))
    await login(client, owner.email)
    res = await client.post(f"/api/v1/seller/products/{product.id}/publish")
    assert res.status_code == 409 and res.json()["error"]["code"] == "product_removed"
    res = await client.post("/api/v1/seller/products/restore", json={"ids": [str(product.id)]})
    assert res.json() == {"updated": 0}

    await login(client, ADMIN)
    open_ids = [g["target_id"] for g in (await client.get(f"{A}/moderation")).json()]
    assert str(product.id) not in open_ids  # its reports are resolved
    resolved = (await client.get(f"{A}/moderation", params={"status": "resolved"})).json()
    assert resolved[0]["resolution"] == "taken_down"
    assert (
        await client.post(f"{A}/moderation/product/{product.id}", json={"action": "restore"})
    ).status_code == 204
    assert (await client.get(f"/api/v1/catalog/products/{product.slug}")).status_code == 200

    # Hide a review: gone from the product page, rating recomputed.
    res = await client.post(
        f"{A}/moderation/review/{review.id}", json={"action": "hide", "note": "Personal attack"}
    )
    assert res.status_code == 204
    r = await shop.scalar(
        select(Review).where(Review.id == review.id).execution_options(populate_existing=True)
    )
    assert r.status == "hidden"
    assert await audited(shop, "moderation.product.remove") == 1
    assert await audited(shop, "moderation.review.hide") == 1

    # Shoppers can't moderate.
    await login(client, BUYER)
    res = await client.post(f"{A}/moderation/review/{review.id}", json={"action": "restore"})
    assert res.status_code == 403
