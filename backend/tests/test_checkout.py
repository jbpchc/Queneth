"""Phase 6: address book, vouchers, save for later, boards and checkout
(multi-boutique split, escrow, idempotency, price/stock re-checks, ownership)."""

import uuid

from sqlalchemy import func, select

from app.core.security import utcnow
from app.db.atomic import atomic
from app.models import SystemWallet, User, Wallet
from app.models.catalog import CartItem, Product, SellerProfile, Variant, WishlistItem
from app.models.commerce import Order, SubOrder, Voucher, VoucherRedemption
from app.models.integration import EmailLog, Notification
from app.services import wallet_service as ws
from tests.conftest import TEST_PASSWORD

CART = "/api/v1/cart"
ORDERS = "/api/v1/orders"
ADDR = "/api/v1/addresses"
BUYER = "buyer@queneth.test"
OTHER = "collector@queneth.test"


async def login(client, email: str) -> None:
    client.cookies.clear()
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert res.status_code == 200, res.text


def idem() -> dict[str, str]:
    return {"Idempotency-Key": uuid.uuid4().hex}


async def user(db, email: str) -> User:
    return await db.scalar(select(User).where(User.email == email))


async def balance(db, email: str) -> int:
    u = await user(db, email)
    w = await db.scalar(
        select(Wallet).where(Wallet.user_id == u.id).execution_options(populate_existing=True)
    )
    return w.balance_qc


async def escrow_balance(db) -> int:
    w = await db.scalar(
        select(Wallet)
        .where(Wallet.system_code == SystemWallet.ESCROW.value)
        .execution_options(populate_existing=True)
    )
    return w.balance_qc


async def variant_from(db, boutique: str, *, min_price: int = 0, max_price: int = 10**9) -> Variant:
    """Cheapest visible, in-stock variant of a boutique within a price band."""
    v = await db.scalar(
        select(Variant)
        .join(Product, Product.id == Variant.product_id)
        .join(SellerProfile, SellerProfile.id == Product.seller_id)
        .where(
            SellerProfile.slug == boutique,
            Product.status == "active",
            Product.deleted_at.is_(None),
            Product.published_at <= utcnow(),
            Variant.stock >= 3,
            Variant.price_qc.between(min_price, max_price),
        )
        .order_by(Variant.price_qc)
        .limit(1)
    )
    assert v is not None, f"no variant for {boutique}"
    return v


async def add(client, variant: Variant, qty: int = 1) -> dict:
    res = await client.post(f"{CART}/items", json={"variant_id": str(variant.id), "qty": qty})
    assert res.status_code == 201, res.text
    return res.json()


async def default_address(client) -> str:
    rows = (await client.get(ADDR)).json()
    return next(a["id"] for a in rows if a["is_default"])


async def pay(client, *, total: int, address: str, pin: str = "123456", headers=None):
    return await client.post(
        f"{ORDERS}/checkout",
        json={"address_id": address, "pin": pin, "expected_total_qc": total},
        headers=headers or idem(),
    )


# ─── Address book ──────────────────────────────────────────────────────────


async def test_address_book(client, shop):
    await login(client, OTHER)  # no seeded addresses
    assert (await client.get(ADDR)).json() == []
    body = {
        "label": "  Home ",
        "recipient": "Ines  Cruz",
        "phone": "0917 555 1234",
        "line1": "4 Acacia Lane",
        "barangay_code": "137602002",
        "zip": "1209",
    }
    first = (await client.post(ADDR, json=body)).json()
    # Postel's Law: phone normalized, spaces squashed; names resolved server-side.
    assert first["phone"] == "+639175551234" and first["recipient"] == "Ines Cruz"
    assert first["city"] == "City of Makati" and first["barangay"] == "Bel-Air"
    assert first["is_default"] is True  # the first address is the default
    second = (
        await client.post(ADDR, json={**body, "label": "Work", "barangay_code": "051724003"})
    ).json()
    assert second["is_default"] is False and second["city"] == "City of Naga"
    # Make the second default, then delete it: the first becomes default again.
    assert (await client.post(f"{ADDR}/{second['id']}/default")).json()["is_default"]
    rows = (await client.get(ADDR)).json()
    assert [r["id"] for r in rows] == [second["id"], first["id"]]
    assert (await client.delete(f"{ADDR}/{second['id']}")).status_code == 204
    assert (await client.get(ADDR)).json()[0]["is_default"] is True

    bad = await client.post(ADDR, json={**body, "phone": "12345"})
    assert bad.status_code == 422
    unknown = await client.post(ADDR, json={**body, "barangay_code": "999999999"})
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "unknown_barangay"

    await login(client, BUYER)  # someone else's address looks missing
    assert (await client.put(f"{ADDR}/{first['id']}", json=body)).status_code == 404
    assert (await client.delete(f"{ADDR}/{first['id']}")).status_code == 404


# ─── Bag: save for later & vouchers ────────────────────────────────────────


async def test_save_for_later(client, shop):
    await login(client, BUYER)
    a = await variant_from(shop, "obra-leather")
    b = await variant_from(shop, "casa-ilaya")
    await add(client, a)
    bag = await add(client, b)
    item = next(i for g in bag["groups"] for i in g["items"] if i["variant_id"] == str(b.id))
    bag = (await client.put(f"{CART}/items/{item['id']}/saved", json={"saved": True})).json()
    assert bag["total_qc"] == a.price_qc and len(bag["saved"]) == 1 and len(bag["groups"]) == 1
    assert (await client.get("/api/v1/me")).status_code == 200
    # Adding it again moves it back into the bag.
    bag = await add(client, b)
    assert bag["saved"] == [] and bag["total_qc"] == a.price_qc + b.price_qc * 2


async def test_vouchers(client, shop):
    await login(client, BUYER)
    lumen = await variant_from(shop, "atelier-lumen", min_price=3_000)
    await add(client, lumen)
    # Postel's Law: code is trimmed and upper-cased.
    bag = (await client.post(f"{CART}/vouchers", json={"code": " lumen10 "})).json()
    group = bag["groups"][0]
    assert group["voucher"]["code"] == "LUMEN10" and group["voucher"]["problem"] is None
    assert group["discount_qc"] == lumen.price_qc * 10 // 100
    assert bag["total_qc"] == lumen.price_qc - group["discount_qc"]

    unknown = await client.post(f"{CART}/vouchers", json={"code": "NOPE-123"})
    assert unknown.status_code == 404
    elsewhere = await client.post(f"{CART}/vouchers", json={"code": "OBRA500"})
    assert elsewhere.json()["error"]["code"] == "voucher_not_applicable"

    # Below minimum spend: the voucher stays, shows how much more to add, discounts 0.
    v = await shop.scalar(select(Voucher).where(Voucher.code == "LUMEN10"))
    v.min_spend_qc = lumen.price_qc + 500
    await shop.commit()
    group = (await client.get(CART)).json()["groups"][0]
    assert group["discount_qc"] == 0 and "500 QC more" in group["voucher"]["problem"]

    bag = (await client.delete(f"{CART}/vouchers/{group['voucher']['id']}")).json()
    assert bag["groups"][0]["voucher"] is None


# ─── Checkout ──────────────────────────────────────────────────────────────


async def test_checkout_splits_per_boutique_into_escrow(client, shop):
    await login(client, BUYER)
    a = await variant_from(shop, "obra-leather")
    b = await variant_from(shop, "nocturne-parfums")
    stock_a, stock_b = a.stock, b.stock
    await add(client, a, 2)
    bag = await add(client, b)
    assert len(bag["groups"]) == 2
    before, escrow_before = await balance(shop, BUYER), await escrow_balance(shop)

    res = await pay(client, total=bag["total_qc"], address=await default_address(client))
    assert res.status_code == 201, res.text
    order = res.json()
    total = a.price_qc * 2 + b.price_qc
    assert order["total_qc"] == total and order["points_pending"] == total // 100
    assert order["number"].startswith(f"QN-{utcnow().year}-")
    numbers = [s["number"] for s in order["sub_orders"]]
    assert numbers == [f"{order['number']}-01", f"{order['number']}-02"]
    assert {s["status"] for s in order["sub_orders"]} == {"PAID"}
    assert all(s["events"][0]["to_status"] == "PAID" for s in order["sub_orders"])
    assert order["shipping_address"]["city"] == "City of Makati"

    # Money: buyer → escrow, one PAYMENT transaction per boutique; ledger balances.
    assert await balance(shop, BUYER) == before - total
    assert await escrow_balance(shop) == escrow_before + total
    subs = (await shop.scalars(select(SubOrder))).all()
    assert len(subs) == 2 and all(s.payment_tx_id for s in subs)
    assert sum(s.commission_qc for s in subs) == sum(ws.commission_for(s.subtotal_qc) for s in subs)
    assert (await ws.reconcile(shop)).ok

    # Stock decremented, bag emptied, email + seller notifications queued.
    await shop.refresh(a)
    await shop.refresh(b)
    assert (a.stock, b.stock) == (stock_a - 2, stock_b - 1)
    assert (await client.get(CART)).json()["groups"] == []
    assert (
        await shop.scalar(
            select(func.count())
            .select_from(EmailLog)
            .where(EmailLog.template == "order_confirmation")
        )
        == 1
    )
    assert (
        await shop.scalar(
            select(func.count()).select_from(Notification).where(Notification.type == "order.new")
        )
        == 2
    )

    # Reads: list + detail; another shopper can't see it.
    listing = (await client.get(ORDERS)).json()
    assert listing["items"][0]["id"] == order["id"] and listing["items"][0]["item_count"] == 3
    assert (await client.get(f"{ORDERS}/{order['id']}")).json()["number"] == order["number"]
    await login(client, OTHER)
    assert (await client.get(f"{ORDERS}/{order['id']}")).status_code == 404
    assert (await client.get(ORDERS)).json()["items"] == []


async def test_checkout_is_idempotent(client, shop):
    await login(client, BUYER)
    bag = await add(client, await variant_from(shop, "obra-leather"))
    address = await default_address(client)
    headers = idem()
    before = await balance(shop, BUYER)
    first = await pay(client, total=bag["total_qc"], address=address, headers=headers)
    again = await pay(client, total=bag["total_qc"], address=address, headers=headers)
    assert first.status_code == 201 and again.status_code == 201
    assert first.json()["id"] == again.json()["id"]
    assert await balance(shop, BUYER) == before - bag["total_qc"]  # charged once
    assert await shop.scalar(select(func.count()).select_from(Order)) == 1


async def test_checkout_with_voucher(client, shop):
    await login(client, BUYER)
    await add(client, await variant_from(shop, "atelier-lumen", min_price=3_000))
    bag = (await client.post(f"{CART}/vouchers", json={"code": "LUMEN10"})).json()
    before = await balance(shop, BUYER)
    res = await pay(client, total=bag["total_qc"], address=await default_address(client))
    assert res.status_code == 201, res.text
    sub = res.json()["sub_orders"][0]
    assert sub["voucher_code"] == "LUMEN10" and sub["discount_qc"] == bag["discount_qc"] > 0
    assert sub["subtotal_qc"] == sub["items_total_qc"] - sub["discount_qc"]
    assert await balance(shop, BUYER) == before - bag["total_qc"]  # seller funds the discount
    v = await shop.scalar(
        select(Voucher).where(Voucher.code == "LUMEN10").execution_options(populate_existing=True)
    )
    assert v.used_count == 1
    assert await shop.scalar(select(func.count()).select_from(VoucherRedemption)) == 1
    # Once per buyer.
    await add(client, await variant_from(shop, "atelier-lumen", min_price=3_000))
    again = await client.post(f"{CART}/vouchers", json={"code": "LUMEN10"})
    assert again.status_code == 409 and "already used" in again.json()["error"]["message"]


async def test_prices_changed_stops_checkout(client, shop):
    await login(client, BUYER)
    v = await variant_from(shop, "obra-leather")
    bag = await add(client, v)
    v.price_qc += 250  # the seller re-prices while the buyer reviews
    await shop.commit()
    before = await balance(shop, BUYER)
    res = await pay(client, total=bag["total_qc"], address=await default_address(client))
    assert res.status_code == 409
    err = res.json()["error"]
    assert err["code"] == "prices_changed" and err["details"]["total_qc"] == bag["total_qc"] + 250
    assert await balance(shop, BUYER) == before
    assert (await client.get(CART)).json()["item_count"] == 1  # nothing lost


async def test_stock_changed_stops_checkout(client, shop):
    await login(client, BUYER)
    v = await variant_from(shop, "obra-leather")
    bag = await add(client, v, 2)
    v.stock = 1
    await shop.commit()
    res = await pay(client, total=bag["total_qc"], address=await default_address(client))
    assert res.status_code == 409
    err = res.json()["error"]
    assert err["code"] == "stock_changed" and err["details"]["items"][0]["available"] == 1


async def test_insufficient_funds(client, shop):
    await login(client, BUYER)
    bag = await add(client, await variant_from(shop, "obra-leather"))
    buyer = await user(shop, BUYER)
    have = await balance(shop, BUYER)
    async with atomic(shop):  # spend most of the wallet elsewhere first
        await ws.pay_into_escrow(shop, buyer.id, have - 10, "test:drain", memo="drain", meta={})
    res = await pay(client, total=bag["total_qc"], address=await default_address(client))
    assert res.status_code == 409
    err = res.json()["error"]
    assert err["code"] == "insufficient_funds"
    assert err["details"]["shortfall_qc"] == bag["total_qc"] - 10
    assert await shop.scalar(select(func.count()).select_from(Order)) == 0


async def test_wrong_pin_and_empty_bag(client, shop):
    await login(client, BUYER)
    address = await default_address(client)
    empty = await pay(client, total=0, address=address)
    assert empty.status_code == 409 and empty.json()["error"]["code"] == "empty_bag"
    bag = await add(client, await variant_from(shop, "obra-leather"))
    wrong = await pay(client, total=bag["total_qc"], address=address, pin="000000")
    assert wrong.status_code == 403
    assert wrong.json()["error"]["details"]["attempts_remaining"] == 4
    assert await shop.scalar(select(func.count()).select_from(Order)) == 0


async def test_cannot_use_someone_elses_address(client, shop):
    await login(client, BUYER)
    address = await default_address(client)
    await login(client, OTHER)
    bag = await add(client, await variant_from(shop, "obra-leather"))
    res = await pay(client, total=bag["total_qc"], address=address)
    assert res.status_code == 404 and res.json()["error"]["code"] == "address_not_found"


async def test_seller_cannot_check_out_own_product(client, shop):
    seller = await user(shop, "seller@queneth.test")
    own = await variant_from(shop, "atelier-lumen")
    shop.add(CartItem(user_id=seller.id, variant_id=own.id, qty=1))  # bypassing the bag guard
    await shop.commit()
    await login(client, "seller@queneth.test")
    res = await pay(client, total=own.price_qc, address=await default_address(client))
    assert res.status_code == 409 and res.json()["error"]["code"] == "own_product"


async def test_saved_for_later_items_are_not_bought(client, shop):
    await login(client, BUYER)
    a = await variant_from(shop, "obra-leather")
    b = await variant_from(shop, "casa-ilaya")
    await add(client, a)
    bag = await add(client, b)
    later = next(i for g in bag["groups"] for i in g["items"] if i["variant_id"] == str(b.id))
    bag = (await client.put(f"{CART}/items/{later['id']}/saved", json={"saved": True})).json()
    res = await pay(client, total=bag["total_qc"], address=await default_address(client))
    assert res.status_code == 201 and len(res.json()["sub_orders"]) == 1
    bag = (await client.get(CART)).json()
    assert bag["groups"] == [] and len(bag["saved"]) == 1


async def test_admin_cannot_check_out(client, shop):
    await login(client, "admin@queneth.test")
    res = await pay(client, total=0, address=str(uuid.uuid4()))
    assert res.status_code == 403


# ─── Wishlist boards ───────────────────────────────────────────────────────


async def test_wishlist_boards(client, shop):
    await login(client, BUYER)
    v = await variant_from(shop, "obra-leather")
    await client.put(f"/api/v1/wishlist/{v.product_id}")
    board = (await client.post("/api/v1/wishlist/boards", json={"name": "Wedding  season"})).json()
    assert board["name"] == "Wedding season"
    dup = await client.post("/api/v1/wishlist/boards", json={"name": "wedding season"})
    assert dup.status_code == 409
    res = await client.put(f"/api/v1/wishlist/{v.product_id}/board", json={"board_id": board["id"]})
    assert res.status_code == 204
    wl = (await client.get("/api/v1/wishlist")).json()
    assert wl["boards"][0]["count"] == 1 and wl["items"][0]["board_id"] == board["id"]
    renamed = await client.patch(f"/api/v1/wishlist/boards/{board['id']}", json={"name": "Gala"})
    assert renamed.json()["name"] == "Gala"
    assert (await client.delete(f"/api/v1/wishlist/boards/{board['id']}")).status_code == 204
    item = await shop.scalar(select(WishlistItem).execution_options(populate_existing=True))
    assert item is not None and item.board_id is None  # the piece stays saved

    await login(client, OTHER)
    other = await client.put(
        f"/api/v1/wishlist/{v.product_id}/board", json={"board_id": board["id"]}
    )
    assert other.status_code == 404
