"""Phase 7: the sub-order state machine, escrow release and refunds, stock
restore, returns, auto-release, Que Points, verified reviews, and who may do what."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.core.security import utcnow
from app.models import SystemWallet, User, Wallet
from app.models.catalog import Product, Review, Variant
from app.models.commerce import (
    Order,
    OrderStatusEvent,
    PointsEntry,
    SubOrder,
    Voucher,
    VoucherRedemption,
)
from app.models.integration import EmailLog, MediaAsset, Notification
from app.services import fulfilment_service as fs
from app.services import wallet_service as ws
from tests.test_checkout import (
    BUYER,
    CART,
    OTHER,
    add,
    balance,
    default_address,
    escrow_balance,
    login,
    pay,
    user,
    variant_from,
)

SELLER = "seller@queneth.test"  # owns Atelier Lumen
SELLER_OPS = "/api/v1/seller/orders"


async def bought(client, db, *, voucher: str | None = None, qty: int = 1) -> dict:
    """Buyer checks out one Atelier Lumen piece; returns the order JSON."""
    await login(client, BUYER)
    await add(client, await variant_from(db, "atelier-lumen", min_price=3_000), qty)
    bag = (await client.get(CART)).json()
    if voucher:
        bag = (await client.post(f"{CART}/vouchers", json={"code": voucher})).json()
    res = await pay(client, total=bag["total_qc"], address=await default_address(client))
    assert res.status_code == 201, res.text
    return res.json()


async def seller_move(client, sub_id: str, to: str, **extra):
    await login(client, SELLER)
    return await client.post(f"{SELLER_OPS}/{sub_id}/status", json={"to": to, **extra})


async def ship_and_deliver(client, sub_id: str) -> None:
    for to, extra in (
        ("PROCESSING", {}),
        ("SHIPPED", {"tracking_no": "qnx 4821-7730"}),
        ("DELIVERED", {}),
    ):
        res = await seller_move(client, sub_id, to, **extra)
        assert res.status_code == 200, res.text


async def wallet_of(db, email: str) -> int:
    return await balance(db, email)


# ─── State machine (unit) ──────────────────────────────────────────────────


def test_transition_map_matches_spec():
    S = fs.S
    assert fs.next_for("PAID", fs.Actor.SELLER) == ["PROCESSING", "CANCELLED"]
    assert fs.next_for("PAID", fs.Actor.BUYER) == ["CANCELLED"]
    assert fs.next_for("SHIPPED", fs.Actor.BUYER) == []
    assert fs.next_for("DELIVERED", fs.Actor.BUYER) == ["COMPLETED", "RETURN_REQUESTED"]
    assert fs.next_for("RETURN_REQUESTED", fs.Actor.SELLER) == ["REFUNDED", "COMPLETED"]
    assert fs.next_for("COMPLETED", fs.Actor.ADMIN) == []  # terminal
    assert (S.SHIPPED, S.CANCELLED) not in fs.TRANSITIONS  # no cancelling after shipping


def test_rollup():
    assert fs.rollup(["PAID", "SHIPPED"]) == "PAID"
    assert fs.rollup(["DELIVERED", "RETURN_REQUESTED"]) == "RETURN_REQUESTED"
    assert fs.rollup(["COMPLETED", "CANCELLED"]) == "COMPLETED"
    assert fs.rollup(["CANCELLED", "CANCELLED"]) == "CANCELLED"
    assert fs.rollup(["REFUNDED"]) == "REFUNDED"


# ─── Happy path ────────────────────────────────────────────────────────────


async def test_full_journey_releases_escrow_and_awards_points(client, shop):
    order = await bought(client, shop)
    sub = order["sub_orders"][0]
    seller_before = await wallet_of(shop, SELLER)
    escrow_before = await escrow_balance(shop)

    # Shipping needs a tracking number (normalized).
    await login(client, SELLER)
    assert (await seller_move(client, sub["id"], "PROCESSING")).status_code == 200
    no_tracking = await seller_move(client, sub["id"], "SHIPPED")
    assert no_tracking.status_code == 422
    assert no_tracking.json()["error"]["code"] == "tracking_required"
    shipped = (await seller_move(client, sub["id"], "SHIPPED", tracking_no="qnx 4821-7730")).json()
    assert shipped["tracking_no"] == "QNX4821-7730" and shipped["next"] == ["DELIVERED"]
    delivered = (await seller_move(client, sub["id"], "DELIVERED")).json()
    assert delivered["auto_release_at"] is not None

    # The buyer sees received/return actions and a return deadline.
    await login(client, BUYER)
    view = (await client.get(f"/api/v1/orders/{order['id']}")).json()["sub_orders"][0]
    assert view["actions"] == ["received", "return"] and view["return_deadline"]
    assert [e["to_status"] for e in view["events"]] == [
        "PAID",
        "PROCESSING",
        "SHIPPED",
        "DELIVERED",
    ]

    done = (await client.post(f"/api/v1/orders/sub-orders/{sub['id']}/received")).json()
    assert done["status"] == "COMPLETED" and done["sub_orders"][0]["actions"] == []
    points = sub["subtotal_qc"] // 100
    assert done["points_earned"] == points and done["points_pending"] == 0

    # Escrow → seller (minus 5 %) and platform revenue; ledger still balances.
    commission = ws.commission_for(sub["subtotal_qc"])
    assert await wallet_of(shop, SELLER) == seller_before + sub["subtotal_qc"] - commission
    assert await escrow_balance(shop) == escrow_before - sub["subtotal_qc"]
    assert (await ws.reconcile(shop)).ok
    buyer = await shop.scalar(
        select(User).where(User.email == BUYER).execution_options(populate_existing=True)
    )
    assert buyer.que_points == points
    assert await shop.scalar(select(func.count()).select_from(PointsEntry)) == 1

    # Double-clicked "Received" is a no-op, not a double release.
    again = await client.post(f"/api/v1/orders/sub-orders/{sub['id']}/received")
    assert again.status_code == 200
    assert await wallet_of(shop, SELLER) == seller_before + sub["subtotal_qc"] - commission

    # Status emails: shipped and delivered went to the buyer.
    templates = set(
        (
            await shop.scalars(select(EmailLog.template).where(EmailLog.template.like("order_%")))
        ).all()
    )
    assert {"order_confirmation", "order_shipped", "order_delivered"} <= templates
    seller_user = await user(shop, SELLER)
    assert (
        await shop.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == seller_user.id, Notification.type == "order.completed")
        )
        == 1
    )


# ─── Cancellation ──────────────────────────────────────────────────────────


async def test_buyer_cancel_refunds_restores_stock_and_frees_voucher(client, shop):
    order = await bought(client, shop, voucher="LUMEN10")
    sub = order["sub_orders"][0]
    variant = await variant_from(shop, "atelier-lumen", min_price=3_000)
    stock_after_buy = await shop.scalar(
        select(Variant.stock)
        .where(Variant.id == variant.id)
        .execution_options(populate_existing=True)
    )
    paid_balance = await wallet_of(shop, BUYER)

    res = await client.post(
        f"/api/v1/orders/sub-orders/{sub['id']}/cancel", json={"reason": "Changed my mind"}
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CANCELLED"
    assert await wallet_of(shop, BUYER) == paid_balance + sub["subtotal_qc"]
    v = await shop.scalar(
        select(Variant).where(Variant.id == variant.id).execution_options(populate_existing=True)
    )
    assert v.stock == stock_after_buy + 1
    p = await shop.scalar(
        select(Product).where(Product.id == v.product_id).execution_options(populate_existing=True)
    )
    assert p.total_stock >= v.stock
    voucher = await shop.scalar(
        select(Voucher).where(Voucher.code == "LUMEN10").execution_options(populate_existing=True)
    )
    assert voucher.used_count == 0
    assert await shop.scalar(select(func.count()).select_from(VoucherRedemption)) == 0
    assert (await ws.reconcile(shop)).ok
    # The seller is told why.
    seller_user = await user(shop, SELLER)
    note = await shop.scalar(
        select(Notification).where(
            Notification.user_id == seller_user.id, Notification.type == "order.cancelled"
        )
    )
    assert "Changed my mind" in note.payload["body"]


async def test_cannot_cancel_after_shipping(client, shop):
    order = await bought(client, shop)
    sub_id = order["sub_orders"][0]["id"]
    assert (await seller_move(client, sub_id, "PROCESSING")).status_code == 200
    assert (
        await seller_move(client, sub_id, "SHIPPED", tracking_no="QNX-123456")
    ).status_code == 200
    await login(client, BUYER)
    res = await client.post(f"/api/v1/orders/sub-orders/{sub_id}/cancel", json={})
    assert res.status_code == 409 and res.json()["error"]["code"] == "invalid_transition"


async def test_seller_cancel_needs_reason(client, shop):
    order = await bought(client, shop)
    sub_id = order["sub_orders"][0]["id"]
    res = await seller_move(client, sub_id, "CANCELLED")
    assert res.status_code == 422 and res.json()["error"]["code"] == "reason_required"
    ok = await seller_move(client, sub_id, "CANCELLED", note="Damaged in our studio")
    assert ok.status_code == 200 and ok.json()["status"] == "CANCELLED"
    assert (
        await shop.scalar(
            select(func.count()).select_from(EmailLog).where(EmailLog.template == "order_cancelled")
        )
        == 1
    )


# ─── Returns ───────────────────────────────────────────────────────────────


async def test_return_approved_refunds(client, shop):
    order = await bought(client, shop)
    sub = order["sub_orders"][0]
    await ship_and_deliver(client, sub["id"])
    await login(client, BUYER)
    short = await client.post(
        f"/api/v1/orders/sub-orders/{sub['id']}/return", json={"reason": "bad"}
    )
    assert short.status_code == 422
    res = await client.post(
        f"/api/v1/orders/sub-orders/{sub['id']}/return",
        json={"reason": "The silk has a pulled thread near the hem."},
    )
    assert res.status_code == 200 and res.json()["status"] == "RETURN_REQUESTED"
    before = await wallet_of(shop, BUYER)
    seller_before = await wallet_of(shop, SELLER)

    # Seller sees the reason and can approve (REFUNDED) or decline (COMPLETED).
    queue = (
        await (await _as(client, SELLER)).get(SELLER_OPS, params={"status": "RETURN_REQUESTED"})
    ).json()
    assert queue["items"][0]["return_reason"].startswith("The silk")
    assert queue["items"][0]["next"] == ["REFUNDED", "COMPLETED"]
    approved = await seller_move(client, sub["id"], "REFUNDED", note="Sorry about that")
    assert approved.status_code == 200
    assert await wallet_of(shop, BUYER) == before + sub["subtotal_qc"]
    assert await wallet_of(shop, SELLER) == seller_before  # nothing released
    assert (await ws.reconcile(shop)).ok


async def test_return_declined_completes_and_releases(client, shop):
    order = await bought(client, shop)
    sub = order["sub_orders"][0]
    await ship_and_deliver(client, sub["id"])
    await login(client, BUYER)
    await client.post(
        f"/api/v1/orders/sub-orders/{sub['id']}/return",
        json={"reason": "Not the shade I expected at all."},
    )
    no_note = await seller_move(client, sub["id"], "COMPLETED")
    assert no_note.status_code == 422
    seller_before = await wallet_of(shop, SELLER)
    res = await seller_move(client, sub["id"], "COMPLETED", note="Colour matches the photos")
    assert res.status_code == 200 and res.json()["status"] == "COMPLETED"
    commission = ws.commission_for(sub["subtotal_qc"])
    assert await wallet_of(shop, SELLER) == seller_before + sub["subtotal_qc"] - commission
    assert (
        await shop.scalar(
            select(func.count()).select_from(EmailLog).where(EmailLog.template == "order_completed")
        )
        == 1
    )


async def test_return_window_closes_after_7_days(client, shop):
    order = await bought(client, shop)
    sub_id = order["sub_orders"][0]["id"]
    await ship_and_deliver(client, sub_id)
    await shop.execute(
        update(SubOrder)
        .where(SubOrder.number == order["sub_orders"][0]["number"])
        .values(delivered_at=utcnow() - timedelta(days=8))
    )
    await shop.commit()
    await login(client, BUYER)
    view = (await client.get(f"/api/v1/orders/{order['id']}")).json()["sub_orders"][0]
    assert view["actions"] == ["received"]
    res = await client.post(
        f"/api/v1/orders/sub-orders/{sub_id}/return",
        json={"reason": "Too late to change my mind now."},
    )
    assert res.status_code == 409 and res.json()["error"]["code"] == "return_window_closed"


# ─── Auto-release & admin ──────────────────────────────────────────────────


async def test_auto_release_after_7_days_and_fast_forward(client, shop):
    first = await bought(client, shop)
    second = await bought(client, shop)
    for o in (first, second):
        await ship_and_deliver(client, o["sub_orders"][0]["id"])
    await shop.execute(
        update(SubOrder)
        .where(SubOrder.number == first["sub_orders"][0]["number"])
        .values(delivered_at=utcnow() - timedelta(days=7, minutes=1))
    )
    await shop.commit()
    # The scheduled job only releases what's due.
    assert await fs.release_due(shop, get_settings()) == 1
    statuses = dict(
        (
            await shop.execute(
                select(SubOrder.number, SubOrder.status).execution_options(populate_existing=True)
            )
        ).all()
    )
    assert statuses[first["sub_orders"][0]["number"]] == "COMPLETED"
    assert statuses[second["sub_orders"][0]["number"]] == "DELIVERED"

    # Buyers and sellers can't use the admin tool; admins fast-forward the rest.
    for email in (BUYER, SELLER):
        await login(client, email)
        assert (
            await client.post("/api/v1/admin/orders/release-due?fast_forward=true")
        ).status_code == 403
    await login(client, "admin@queneth.test")
    res = await client.post("/api/v1/admin/orders/release-due?fast_forward=true")
    assert res.json() == {"released": 1}
    assert (await ws.reconcile(shop)).ok
    system_event = await shop.scalar(
        select(OrderStatusEvent).where(
            OrderStatusEvent.to_status == "COMPLETED", OrderStatusEvent.actor_id.is_(None)
        )
    )
    assert system_event is not None  # the clock, not a person


async def test_admin_override_is_audited(client, shop):
    order = await bought(client, shop)
    sub_id = order["sub_orders"][0]["id"]
    await login(client, "admin@queneth.test")
    res = await client.post(
        f"/api/v1/admin/orders/{sub_id}/status", json={"to": "CANCELLED", "note": "Fraud check"}
    )
    assert res.status_code == 200 and res.json() == {"released": 1}
    from app.models.user import AuditLog

    assert (
        await shop.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "order.override")
        )
        == 1
    )


# ─── Authorization ─────────────────────────────────────────────────────────


async def test_who_may_move_what(client, shop):
    order = await bought(client, shop)
    sub_id = order["sub_orders"][0]["id"]
    # The buyer can't ship their own order.
    await login(client, BUYER)
    res = await client.post(f"{SELLER_OPS}/{sub_id}/status", json={"to": "PROCESSING"})
    assert res.status_code == 403  # buyers lack order:fulfill
    # Another boutique's seller can't see or move it.
    await login(client, "verde@queneth.test")
    assert (await client.get(f"{SELLER_OPS}/{sub_id}")).status_code == 404
    res = await client.post(f"{SELLER_OPS}/{sub_id}/status", json={"to": "PROCESSING"})
    assert res.status_code == 404
    assert all(i["id"] != sub_id for i in (await client.get(SELLER_OPS)).json()["items"])
    # Another shopper can't cancel it.
    await login(client, OTHER)
    res = await client.post(f"/api/v1/orders/sub-orders/{sub_id}/cancel", json={})
    assert res.status_code == 404
    # The seller can't mark it received for the buyer.
    await ship_and_deliver(client, sub_id)
    res = await seller_move(client, sub_id, "COMPLETED")
    assert res.status_code == 403 and res.json()["error"]["code"] == "transition_not_allowed"
    # Unknown jumps are rejected.
    res = await seller_move(client, sub_id, "PAID")
    assert res.status_code == 409


async def test_seller_queue_counts_and_filter(client, shop):
    await bought(client, shop)
    o2 = await bought(client, shop)
    await seller_move(client, o2["sub_orders"][0]["id"], "PROCESSING")
    await login(client, SELLER)
    q = (await client.get(SELLER_OPS)).json()
    assert q["counts"] == {"PAID": 1, "PROCESSING": 1}
    item = q["items"][0]
    assert item["net_qc"] == item["subtotal_qc"] - item["commission_qc"]
    assert item["buyer_name"] and item["shipping_address"]["city"]
    only = (await client.get(SELLER_OPS, params={"status": "PAID"})).json()["items"]
    assert len(only) == 1 and only[0]["status"] == "PAID"


# ─── Reviews ───────────────────────────────────────────────────────────────


async def test_verified_review_once_per_line(client, shop):
    order = await bought(client, shop)
    sub = order["sub_orders"][0]
    item_id = sub["items"][0]["id"]
    await login(client, BUYER)
    body = {
        "order_item_id": item_id,
        "rating": 5,
        "fit": "true",
        "body": "Beautiful drape and colour.",
    }
    early = await client.post("/api/v1/reviews", json=body)
    assert early.status_code == 409 and early.json()["error"]["code"] == "not_delivered"

    await ship_and_deliver(client, sub["id"])
    await login(client, BUYER)
    view = (await client.get(f"/api/v1/orders/{order['id']}")).json()
    assert view["sub_orders"][0]["items"][0]["can_review"] is True

    # A review photo uploaded through the media flow (local fallback in tests).
    buyer = await user(shop, BUYER)
    asset = MediaAsset(
        owner_id=buyer.id,
        purpose="review",
        provider="local",
        status="ready",
        public_id="review/test",
        url="/media/review/test.jpg",
        content_type="image/jpeg",
        bytes=1000,
    )
    shop.add(asset)
    await shop.commit()
    product = await shop.scalar(
        select(Product).where(Product.slug == sub["items"][0]["product_slug"])
    )
    count_before = product.rating_count
    res = await client.post("/api/v1/reviews", json={**body, "photo_asset_ids": [str(asset.id)]})
    assert res.status_code == 201, res.text
    review = await shop.scalar(select(Review).where(Review.order_item_id == uuid.UUID(item_id)))
    assert review.photos and review.photos[0].endswith("/media/review/test.jpg")
    product = await shop.scalar(
        select(Product).where(Product.id == product.id).execution_options(populate_existing=True)
    )
    assert product.rating_count == count_before + 1

    dup = await client.post("/api/v1/reviews", json=body)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "already_reviewed"
    view = (await client.get(f"/api/v1/orders/{order['id']}")).json()
    line = view["sub_orders"][0]["items"][0]
    assert line["review_id"] == res.json()["id"] and line["can_review"] is False

    # Someone else can't review the buyer's purchase.
    await login(client, OTHER)
    other = await client.post("/api/v1/reviews", json=body)
    assert other.status_code == 404


async def _as(client, email):
    await login(client, email)
    return client


@pytest.mark.parametrize("unused", [None])
async def test_escrow_wallet_never_negative_after_mixed_flows(client, shop, unused):
    a = await bought(client, shop)
    b = await bought(client, shop)
    await login(client, BUYER)
    await client.post(f"/api/v1/orders/sub-orders/{a['sub_orders'][0]['id']}/cancel", json={})
    await ship_and_deliver(client, b["sub_orders"][0]["id"])
    await login(client, BUYER)
    await client.post(f"/api/v1/orders/sub-orders/{b['sub_orders'][0]['id']}/received")
    escrow = await shop.scalar(
        select(Wallet)
        .where(Wallet.system_code == SystemWallet.ESCROW.value)
        .execution_options(populate_existing=True)
    )
    assert escrow.balance_qc >= 0
    orders = (await shop.scalars(select(Order).execution_options(populate_existing=True))).all()
    assert sorted(o.status for o in orders) == ["CANCELLED", "COMPLETED"]
    assert (await ws.reconcile(shop)).ok


async def test_order_history_seed_covers_every_status(shop):
    from app.seed.orders import seed_orders

    assert await seed_orders(shop) == 8
    assert await seed_orders(shop) == 0  # idempotent
    statuses = set(
        (
            await shop.scalars(select(SubOrder.status).execution_options(populate_existing=True))
        ).all()
    )
    assert statuses == {
        "PAID",
        "PROCESSING",
        "SHIPPED",
        "DELIVERED",
        "COMPLETED",
        "CANCELLED",
        "RETURN_REQUESTED",
        "REFUNDED",
    }
    assert (await ws.reconcile(shop)).ok
    marco = await shop.scalar(
        select(User).where(User.email == OTHER).execution_options(populate_existing=True)
    )
    assert marco.que_points > 0
