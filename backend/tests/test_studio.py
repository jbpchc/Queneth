"""Phase 8: Seller Studio — application & approval, product wizard, inventory,
dashboard, earnings, drops, vouchers, review replies, storefront settings,
and that one boutique can never touch another's data."""

import uuid
from datetime import timedelta

from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.core.security import utcnow
from app.models import User
from app.models.catalog import Drop, DropSubscription, Product, Review, SellerProfile, Variant
from app.models.integration import EmailLog, MediaAsset, Notification
from app.services import studio_service
from tests.test_checkout import add, default_address, login, pay, user, variant_from

S = "/api/v1/seller"
SELLER = "nocturne@queneth.test"  # Nocturne Parfums
OTHER_SELLER = "obra@queneth.test"  # Obra Leather
BUYER = "buyer@queneth.test"
ADMIN = "admin@queneth.test"

APPLICATION = {
    "boutique_name": "Atelier Mira",
    "tagline": "Hand-finished linen from Cebu",
    "bio": "Atelier Mira cuts small runs of linen and ramie, finished by hand in our Cebu studio.",
    "return_policy": "Returns within 7 days if unworn, tags attached.",
    "contact_email": "hello@mira.test",
    "city": "Cebu",
}

PERFUME_ATTRS = {
    "concentration": "EDP",
    "family": "Citrus",
    "top_notes": ["Bergamot", " calamansi "],
    "heart_notes": ["neroli"],
    "base_notes": ["vetiver"],
    "perfumer": "Ines Cruz",
    "longevity": 4,
    "sillage": 3,
}


async def asset(db, email: str, purpose: str = "product") -> MediaAsset:
    owner = await user(db, email)
    a = MediaAsset(
        owner_id=owner.id,
        purpose=purpose,
        provider="local",
        public_id=f"{purpose}/{uuid.uuid4().hex}",
        status="ready",
        url=f"/media/{purpose}/{uuid.uuid4().hex}.jpg",
        content_type="image/jpeg",
        bytes=1000,
    )
    db.add(a)
    await db.commit()
    return a


async def ready_product(client, db, *, publish: bool = True) -> dict:
    """Seller (Nocturne Parfums) walks the wizard to a complete perfume."""
    await login(client, SELLER)
    res = await client.post(
        f"{S}/products",
        json={
            "title": "Calamansi Hour",
            "brand": "Lumen Atelier",
            "category": "perfumes",
            "subcategory": "unisex",
        },
    )
    assert res.status_code == 201, res.text
    pid = res.json()["id"]
    a = await asset(db, SELLER)
    body = {
        "description": "A bright Filipino citrus: calamansi and bergamot over clean vetiver.",
        "attributes": PERFUME_ATTRS,
        "images": [{"asset_id": str(a.id), "alt": "Calamansi Hour bottle, front"}],
        "variants": [
            {"options": {"volume": "50 ml"}, "price_qc": 4200, "stock": 5},
            {"options": {"volume": "100 ml"}, "price_qc": 6800, "compare_at_qc": 7500, "stock": 2},
        ],
    }
    res = await client.patch(f"{S}/products/{pid}", json=body)
    assert res.status_code == 200, res.text
    if publish:
        res = await client.post(f"{S}/products/{pid}/publish")
        assert res.status_code == 200, res.text
    return res.json()


# ─── Application & approval ────────────────────────────────────────────────


async def test_apply_approve_and_reject(client, shop):
    await login(client, "collector@queneth.test")
    assert (await client.get("/api/v1/seller-application")).json() is None
    res = await client.put("/api/v1/seller-application", json={**APPLICATION, "bio": "Too short"})
    assert res.status_code == 422
    taken = await client.put(
        "/api/v1/seller-application", json={**APPLICATION, "boutique_name": "nocturne parfums"}
    )
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "boutique_name_taken"
    app_ = (await client.put("/api/v1/seller-application", json=APPLICATION)).json()
    assert app_["status"] == "pending" and app_["slug"] == "atelier-mira"
    # Pending applicants can't use the Studio.
    assert (await client.get(f"{S}/dashboard")).status_code == 403

    # Only admins decide.
    await login(client, SELLER)
    assert (await client.post(f"/api/v1/admin/sellers/{app_['id']}/approve")).status_code == 403
    await login(client, ADMIN)
    pending = (await client.get("/api/v1/admin/sellers/pending")).json()
    assert [p["boutique_name"] for p in pending] == ["Atelier Mira"]
    no_reason = await client.post(f"/api/v1/admin/sellers/{app_['id']}/reject", json={})
    assert no_reason.status_code == 422
    rejected = await client.post(
        f"/api/v1/admin/sellers/{app_['id']}/reject", json={"reason": "Add photos of your studio."}
    )
    assert rejected.json()["status"] == "rejected"

    # Resubmitting puts it back in the queue, then approval grants the SELLER role.
    await login(client, "collector@queneth.test")
    mine = (await client.get("/api/v1/seller-application")).json()
    assert mine["rejection_reason"] == "Add photos of your studio."
    again = (await client.put("/api/v1/seller-application", json=APPLICATION)).json()
    assert again["status"] == "pending" and again["rejection_reason"] is None
    await login(client, ADMIN)
    assert (await client.post(f"/api/v1/admin/sellers/{app_['id']}/approve")).status_code == 200
    marco = await shop.scalar(
        select(User)
        .where(User.email == "collector@queneth.test")
        .execution_options(populate_existing=True)
    )
    assert "SELLER" in marco.roles
    templates = set((await shop.scalars(select(EmailLog.template))).all())
    assert {"seller_approved", "seller_rejected"} <= templates
    await login(client, "collector@queneth.test")
    dash = (await client.get(f"{S}/dashboard")).json()
    assert dash["boutique"] == "Atelier Mira" and dash["product_count"] == 0
    # An approved seller can't apply again.
    res = await client.put("/api/v1/seller-application", json=APPLICATION)
    assert res.status_code in (403, 409)


# ─── Product wizard ────────────────────────────────────────────────────────


async def test_wizard_draft_autosave_and_publish(client, shop):
    await login(client, SELLER)
    meta = (await client.get(f"{S}/products/meta")).json()
    perfumes = next(c for c in meta["categories"] if c["slug"] == "perfumes")
    assert perfumes["variant_axes"] == ["volume"] and perfumes["attribute_schema"]

    draft = (
        await client.post(
            f"{S}/products",
            json={
                "title": "  Calamansi   Hour ",
                "brand": "Lumen Atelier",
                "category": "perfumes",
                "subcategory": "unisex",
            },
        )
    ).json()
    assert draft["status"] == "draft" and draft["title"] == "Calamansi Hour"
    assert len(draft["missing"]) >= 3
    # Partial attributes are fine in a draft (autosave).
    res = await client.patch(
        f"{S}/products/{draft['id']}", json={"attributes": {"family": "Citrus", "bogus": 1}}
    )
    assert res.status_code == 200 and res.json()["attributes"] == {"family": "Citrus"}
    early = await client.post(f"{S}/products/{draft['id']}/publish")
    assert early.status_code == 422 and early.json()["error"]["code"] == "incomplete_product"
    bad_axis = await client.patch(
        f"{S}/products/{draft['id']}",
        json={"variants": [{"options": {"size": "M"}, "price_qc": 100, "stock": 1}]},
    )
    assert bad_axis.status_code == 422
    fake_markdown = await client.patch(
        f"{S}/products/{draft['id']}",
        json={
            "variants": [
                {"options": {"volume": "50 ml"}, "price_qc": 500, "compare_at_qc": 400, "stock": 1}
            ]
        },
    )
    assert fake_markdown.status_code == 422

    product = await ready_product(client, shop)
    assert product["status"] == "active" and product["missing"] == []
    assert product["attributes"]["top_notes"] == ["bergamot", "calamansi"]  # normalized
    public = await client.get(f"/api/v1/catalog/products/{product['slug']}")
    assert public.status_code == 200
    # A live piece must stay complete.
    res = await client.patch(f"{S}/products/{product['id']}", json={"images": []})
    assert res.status_code == 422 and "photo" in res.json()["error"]["message"]
    # Reorder: keep the existing image by URL, add another upload first.
    second = await asset(shop, SELLER)
    res = await client.patch(
        f"{S}/products/{product['id']}",
        json={
            "images": [
                {"asset_id": str(second.id), "alt": "Bottle, detail"},
                {"url": product["images"][0]["url"], "alt": "Bottle, front"},
            ]
        },
    )
    assert [i["alt"] for i in res.json()["images"]] == ["Bottle, detail", "Bottle, front"]
    # Someone else's upload can't be attached.
    foreign = await asset(shop, OTHER_SELLER)
    res = await client.patch(
        f"{S}/products/{product['id']}",
        json={"images": [{"asset_id": str(foreign.id), "alt": "Not mine"}]},
    )
    assert res.status_code == 404


async def test_duplicate_archive_restore_delete(client, shop):
    product = await ready_product(client, shop)
    copy = (await client.post(f"{S}/products/{product['id']}/duplicate")).json()
    assert copy["status"] == "draft" and copy["title"] == "Calamansi Hour (copy)"
    assert all(v["stock"] == 0 for v in copy["variants"])
    assert {v["sku"] for v in copy["variants"]}.isdisjoint({v["sku"] for v in product["variants"]})

    res = await client.post(f"{S}/products/archive", json={"ids": [product["id"]]})
    assert res.json() == {"updated": 1}
    assert (await client.get(f"/api/v1/catalog/products/{product['slug']}")).status_code == 404
    await client.post(f"{S}/products/restore", json={"ids": [product["id"]]})
    assert (await client.get(f"/api/v1/catalog/products/{product['slug']}")).status_code == 200

    page = (await client.get(f"{S}/products", params={"status": "draft"})).json()
    assert [r["id"] for r in page["items"]] == [copy["id"]]
    assert page["counts"]["active"] >= 1
    assert (await client.delete(f"{S}/products/{product['id']}")).status_code == 409
    assert (await client.delete(f"{S}/products/{copy['id']}")).status_code == 204


async def test_boutiques_are_isolated(client, shop):
    product = await ready_product(client, shop)
    await login(client, OTHER_SELLER)
    assert (await client.get(f"{S}/products/{product['id']}")).status_code == 404
    assert (
        await client.patch(f"{S}/products/{product['id']}", json={"title": "Mine now"})
    ).status_code == 404
    res = await client.post(f"{S}/products/archive", json={"ids": [product["id"]]})
    assert res.status_code == 404
    assert all(
        r["id"] != product["id"] for r in (await client.get(f"{S}/products")).json()["items"]
    )
    res = await client.patch(
        f"{S}/inventory",
        json={"updates": [{"variant_id": product["variants"][0]["id"], "stock": 99}]},
    )
    assert res.status_code == 404
    # Shoppers have no Studio at all.
    await login(client, BUYER)
    assert (await client.get(f"{S}/products")).status_code == 403
    assert (await client.get(f"{S}/dashboard")).status_code == 403


# ─── Inventory ─────────────────────────────────────────────────────────────


async def test_inventory_inline_edit(client, shop):
    product = await ready_product(client, shop)
    low = (await client.get(f"{S}/inventory", params={"low": "true"})).json()
    big = next(v for v in product["variants"] if v["options"]["volume"] == "100 ml")
    assert any(r["variant_id"] == big["id"] for r in low)  # stock 2 ≤ threshold 3
    res = await client.patch(
        f"{S}/inventory",
        json={"updates": [{"variant_id": big["id"], "stock": 12, "low_stock_threshold": 2}]},
    )
    assert res.json() == {"updated": 1}
    p = await shop.scalar(
        select(Product)
        .where(Product.id == uuid.UUID(product["id"]))
        .execution_options(populate_existing=True)
    )
    assert p.total_stock == 5 + 12


# ─── Dashboard & earnings ──────────────────────────────────────────────────


async def test_dashboard_first_sale_and_earnings(client, shop):
    await login(client, SELLER)
    before = (await client.get(f"{S}/dashboard")).json()
    assert before["first_sale"] is False and len(before["series"]) == 30

    await login(client, BUYER)
    v = await variant_from(shop, "nocturne-parfums", min_price=4_000)
    bag = await add(client, v)
    order = (await pay(client, total=bag["total_qc"], address=await default_address(client))).json()
    sub = order["sub_orders"][0]

    await login(client, SELLER)
    dash = (await client.get(f"{S}/dashboard")).json()
    assert dash["today_revenue_qc"] == sub["subtotal_qc"] and dash["today_orders"] == 1
    assert dash["to_fulfil"] == 1 and dash["first_sale"] is True
    assert dash["series"][-1]["revenue_qc"] == sub["subtotal_qc"]
    assert dash["funnel"]["bag_adds"] >= 1 and dash["funnel"]["orders"] == 1
    assert dash["top_products"][0]["units"] == 1
    assert (await client.post(f"{S}/first-sale/dismiss")).status_code == 204
    assert (await client.get(f"{S}/dashboard")).json()["first_sale"] is False

    from app.services import wallet_service as ws

    held = sub["subtotal_qc"] - ws.commission_for(sub["subtotal_qc"])
    earn = (await client.get(f"{S}/earnings")).json()
    assert earn["in_escrow_qc"] == held and earn["released_qc"] == 0
    assert (await client.get("/api/v1/wallet")).json()["pending_qc"] == held


# ─── Drops ─────────────────────────────────────────────────────────────────


async def test_drop_schedules_hides_and_notifies(client, shop):
    draft = await ready_product(client, shop, publish=False)
    starts = (utcnow() + timedelta(days=2)).isoformat()
    too_soon = await client.post(
        f"{S}/drops",
        json={
            "title": "Monsoon Edit",
            "starts_at": utcnow().isoformat(),
            "product_ids": [draft["id"]],
        },
    )
    assert too_soon.status_code == 422
    drop = (
        await client.post(
            f"{S}/drops",
            json={"title": "Monsoon Edit", "starts_at": starts, "product_ids": [draft["id"]]},
        )
    ).json()
    assert drop["state"] == "scheduled" and drop["products"] == ["Calamansi Hour"]
    # Scheduled: active but invisible until the drop starts (no early peeks).
    p = await shop.scalar(select(Product).where(Product.id == uuid.UUID(draft["id"])))
    assert p.status == "active" and p.published_at > utcnow()
    assert (await client.get(f"/api/v1/catalog/products/{draft['slug']}")).status_code == 404
    clash = await client.post(
        f"{S}/drops",
        json={"title": "Second", "starts_at": starts, "product_ids": [draft["id"]]},
    )
    assert clash.status_code == 409

    # A shopper asks to be notified, then the drop goes live.
    await login(client, BUYER)
    assert (await client.put(f"/api/v1/catalog/drops/{drop['slug']}/notify")).status_code in (
        200,
        204,
    )
    await shop.execute(
        update(Drop)
        .where(Drop.id == uuid.UUID(drop["id"]))
        .values(starts_at=utcnow() - timedelta(minutes=1))
    )
    await shop.execute(
        update(Product)
        .where(Product.id == uuid.UUID(draft["id"]))
        .values(published_at=utcnow() - timedelta(minutes=1))
    )
    await shop.commit()
    assert await studio_service.notify_live_drops(shop, get_settings()) == 1
    assert await studio_service.notify_live_drops(shop, get_settings()) == 0  # once only
    sub = await shop.scalar(select(DropSubscription).execution_options(populate_existing=True))
    assert sub.notified_at is not None
    assert (
        await shop.scalar(
            select(func.count()).select_from(EmailLog).where(EmailLog.template == "drop_live")
        )
        == 1
    )

    # Live drops can't be edited or deleted.
    await login(client, SELLER)
    assert (await client.delete(f"{S}/drops/{drop['id']}")).status_code == 409


async def test_cancelling_a_scheduled_drop_returns_pieces_to_drafts(client, shop):
    draft = await ready_product(client, shop, publish=False)
    drop = (
        await client.post(
            f"{S}/drops",
            json={
                "title": "Rain Edit",
                "starts_at": (utcnow() + timedelta(days=1)).isoformat(),
                "product_ids": [draft["id"]],
            },
        )
    ).json()
    assert (await client.delete(f"{S}/drops/{drop['id']}")).status_code == 204
    p = await shop.scalar(
        select(Product)
        .where(Product.id == uuid.UUID(draft["id"]))
        .execution_options(populate_existing=True)
    )
    assert p.status == "draft" and p.published_at is None


# ─── Vouchers ──────────────────────────────────────────────────────────────


async def test_voucher_crud(client, shop):
    await login(client, SELLER)
    res = await client.post(
        f"{S}/vouchers", json={"code": " mira 15 ", "type": "percent", "value": 15}
    )
    assert res.status_code == 201 and res.json()["code"] == "MIRA15"
    assert res.json()["state"] == "active"
    dup = await client.post(f"{S}/vouchers", json={"code": "MIRA15", "type": "fixed", "value": 100})
    assert dup.status_code == 409
    too_big = await client.post(
        f"{S}/vouchers", json={"code": "HUGE95", "type": "percent", "value": 95}
    )
    assert too_big.status_code == 422
    vid = res.json()["id"]
    paused = (await client.patch(f"{S}/vouchers/{vid}", json={"is_active": False})).json()
    assert paused["state"] == "paused"
    assert (await client.delete(f"{S}/vouchers/{vid}")).status_code == 204

    # A used voucher stays on record.
    await login(client, BUYER)
    await add(client, await variant_from(shop, "nocturne-parfums", min_price=4_000))
    bag = (await client.post("/api/v1/cart/vouchers", json={"code": "NOCTURNE15"})).json()
    await pay(client, total=bag["total_qc"], address=await default_address(client))
    await login(client, SELLER)
    lumen = next(v for v in (await client.get(f"{S}/vouchers")).json() if v["code"] == "NOCTURNE15")
    assert lumen["used_count"] == 1 and lumen["discount_given_qc"] > 0
    assert (await client.delete(f"{S}/vouchers/{lumen['id']}")).status_code == 409
    # Another boutique can't see or change it.
    await login(client, OTHER_SELLER)
    assert all(v["code"] != "NOCTURNE15" for v in (await client.get(f"{S}/vouchers")).json())
    assert (
        await client.patch(f"{S}/vouchers/{lumen['id']}", json={"is_active": False})
    ).status_code == 404


# ─── Reviews ───────────────────────────────────────────────────────────────


async def test_review_reply(client, shop):
    await login(client, SELLER)
    reviews = (await client.get(f"{S}/reviews", params={"unreplied": "true"})).json()
    assert reviews, "the seed has reviews for Nocturne Parfums"
    target = reviews[0]
    res = await client.put(f"{S}/reviews/{target['id']}/reply", json={"reply": "Thank you, truly."})
    assert res.status_code == 200 and res.json()["seller_reply"] == "Thank you, truly."
    review = await shop.scalar(select(Review).where(Review.id == uuid.UUID(target["id"])))
    assert (
        await shop.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == review.buyer_id, Notification.type == "review.reply")
        )
        == 1
    )
    await login(client, OTHER_SELLER)
    res = await client.put(f"{S}/reviews/{target['id']}/reply", json={"reply": "Not my review"})
    assert res.status_code == 404


# ─── Storefront settings ───────────────────────────────────────────────────


async def test_storefront_settings(client, shop):
    product = await ready_product(client, shop)
    current = (await client.get(f"{S}/settings")).json()
    logo = await asset(shop, SELLER, "boutique")
    look = await asset(shop, SELLER, "boutique")
    body = {
        "tagline": "Quiet luxury, cut in Manila.",
        "bio": current["bio"],
        "return_policy": current["return_policy"] or "Returns within 7 days if unworn.",
        "contact_email": "studio@lumen.test",
        "city": "Manila",
        "logo_asset_id": str(logo.id),
        "featured_product_ids": [product["id"]],
        "lookbook": [{"asset_id": str(look.id), "caption": "Rainy-season linens"}],
    }
    res = await client.put(f"{S}/settings", json=body)
    assert res.status_code == 200, res.text
    saved = res.json()
    assert (
        saved["logo_url"].endswith(logo.url)
        and saved["lookbook"][0]["caption"] == "Rainy-season linens"
    )
    # Re-saving keeps the existing lookbook image by URL.
    res = await client.put(
        f"{S}/settings",
        json={**body, "logo_asset_id": None, "lookbook": [{"url": saved["lookbook"][0]["url"]}]},
    )
    assert res.status_code == 200 and len(res.json()["lookbook"]) == 1

    page = (await client.get("/api/v1/catalog/boutiques/nocturne-parfums")).json()
    assert [c["id"] for c in page["featured"]] == [product["id"]] and page["lookbook"]

    # Another boutique's piece can't be featured.
    other = await variant_from(shop, "obra-leather")
    res = await client.put(
        f"{S}/settings", json={**body, "featured_product_ids": [str(other.product_id)]}
    )
    assert res.status_code == 422


async def test_seller_profile_counts(shop):
    assert await shop.scalar(select(func.count()).select_from(SellerProfile)) == 7
    assert await shop.scalar(select(func.count()).select_from(Variant)) > 100
