"""Sub-order state machine (spec §11), with the money and stock side effects.

Every move goes through `transition()`:

- the sub-order row is locked (``FOR UPDATE``), so two people can't move it at once;
- the (from, to) pair must be in TRANSITIONS and the actor's kind must be allowed;
- side effects run in the same database transaction:
    CANCELLED / REFUNDED → escrow back to the buyer, stock restored, voucher freed
    SHIPPED              → tracking number required
    RETURN_REQUESTED     → reason required, within 7 days of delivery
    COMPLETED            → escrow to the seller minus 5 %, Que Points to the buyer
- an OrderStatusEvent is written, the parent order's status is rolled up, and
  the other party is notified (status emails go to the buyer).

Repeating a move that already happened (a double-clicked "Received") is a
no-op, not an error.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.core.permissions import Permission, can
from app.core.security import as_aware, utcnow
from app.db.atomic import atomic
from app.models.catalog import Product, SellerProfile, Variant
from app.models.commerce import (
    Order,
    OrderItem,
    OrderStatusEvent,
    PointsEntry,
    SubOrder,
    Voucher,
    VoucherRedemption,
)
from app.models.commerce import OrderStatus as S
from app.models.integration import EmailLog, Notification
from app.models.user import User
from app.services import email_service, email_templates
from app.services import wallet_service as ws
from app.services.catalog_index import refresh_denormalized

log = structlog.get_logger(__name__)

RETURN_WINDOW = timedelta(days=7)
AUTO_RELEASE_AFTER = timedelta(days=7)
POINTS_PER_QC = 100
TRACKING_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{5,39}$")


class Actor(StrEnum):
    BUYER = "buyer"
    SELLER = "seller"
    ADMIN = "admin"
    SYSTEM = "system"


B, SE, AD, SY = Actor.BUYER, Actor.SELLER, Actor.ADMIN, Actor.SYSTEM

#: The only legal moves. Anything not listed is rejected.
TRANSITIONS: dict[tuple[S, S], frozenset[Actor]] = {
    (S.PAID, S.PROCESSING): frozenset({SE, AD}),
    (S.PAID, S.CANCELLED): frozenset({B, SE, AD}),
    (S.PROCESSING, S.CANCELLED): frozenset({B, SE, AD}),
    (S.PROCESSING, S.SHIPPED): frozenset({SE, AD}),
    (S.SHIPPED, S.DELIVERED): frozenset({SE, AD}),
    (S.DELIVERED, S.COMPLETED): frozenset({B, SY, AD}),
    (S.DELIVERED, S.RETURN_REQUESTED): frozenset({B}),
    (S.RETURN_REQUESTED, S.REFUNDED): frozenset({SE, AD}),
    (S.RETURN_REQUESTED, S.COMPLETED): frozenset({SE, AD}),
}

ACTIVE = (S.RETURN_REQUESTED, S.PAID, S.PROCESSING, S.SHIPPED, S.DELIVERED)


def next_for(status: str, actor: Actor) -> list[str]:
    return [to.value for (frm, to), who in TRANSITIONS.items() if frm == status and actor in who]


def rollup(statuses: list[str]) -> str:
    """Parent order status: the sub-order that needs attention first; once all
    are finished, COMPLETED unless every one was cancelled or refunded."""
    for s in ACTIVE:
        if s.value in statuses:
            return s.value
    if all(s == S.CANCELLED for s in statuses):
        return S.CANCELLED.value
    if all(s == S.REFUNDED for s in statuses):
        return S.REFUNDED.value
    return S.COMPLETED.value


def return_deadline(sub: SubOrder) -> datetime | None:
    return as_aware(sub.delivered_at) + RETURN_WINDOW if sub.delivered_at else None


def auto_release_at(sub: SubOrder) -> datetime | None:
    if sub.status != S.DELIVERED or not sub.delivered_at:
        return None
    return as_aware(sub.delivered_at) + AUTO_RELEASE_AFTER


def buyer_actions(sub: SubOrder, now: datetime | None = None) -> list[str]:
    now = now or utcnow()
    out: list[str] = []
    if sub.status in (S.PAID, S.PROCESSING):
        out.append("cancel")
    if sub.status == S.DELIVERED:
        out.append("received")
        deadline = return_deadline(sub)
        if deadline and now <= deadline:
            out.append("return")
    return out


def actor_for(user: User | None, sub: SubOrder, order: Order) -> Actor:
    """Who is acting on this sub-order. Strangers get a 404 (no IDOR)."""
    if user is None:
        return SY
    if can(user, Permission.ORDER_OVERRIDE):
        return AD
    if (
        user.seller_id is not None
        and user.seller_id == sub.seller_id
        and can(user, Permission.ORDER_FULFILL)
    ):
        return SE
    if order.buyer_id == user.id and can(user, Permission.ORDER_VIEW):
        return B
    raise NotFound("We couldn't find that order.", code="order_not_found")


@dataclass
class Moved:
    sub: SubOrder
    emails: list[EmailLog]
    changed: bool


async def transition(
    session: AsyncSession,
    settings: Settings,
    user: User | None,
    sub_id: uuid.UUID,
    to: str,
    *,
    note: str | None = None,
    tracking_no: str | None = None,
    reason: str | None = None,
    now: datetime | None = None,
) -> Moved:
    now = now or utcnow()
    target = S(to)
    emails: list[EmailLog] = []
    async with atomic(session):
        sub = await session.scalar(
            select(SubOrder)
            .where(SubOrder.id == sub_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if sub is None:
            raise NotFound("We couldn't find that order.", code="order_not_found")
        order = await session.get(Order, sub.order_id)
        assert order is not None
        actor = actor_for(user, sub, order)
        current = S(sub.status)
        if current == target:
            return Moved(sub, [], changed=False)  # idempotent repeat
        allowed = TRANSITIONS.get((current, target))
        if allowed is None:
            raise Conflict(
                f"This order is {current.value.lower().replace('_', ' ')} and can't become "
                f"{target.value.lower().replace('_', ' ')}.",
                code="invalid_transition",
                details={"from": current.value, "to": target.value},
            )
        if actor not in allowed:
            raise PermissionDenied(
                "You can't make this change to the order.",
                code="transition_not_allowed",
                details={"from": current.value, "to": target.value, "actor": actor.value},
            )

        seller = await session.get(SellerProfile, sub.seller_id)
        buyer = await session.get(User, order.buyer_id)
        assert seller is not None and buyer is not None
        event_note = note

        if target == S.SHIPPED:
            code = "".join((tracking_no or "").split()).upper()
            if not TRACKING_RE.match(code):
                raise ValidationFailed(
                    "Add a tracking number (6–40 letters, digits or dashes).",
                    code="tracking_required",
                )
            sub.tracking_no = code
            sub.shipped_at = now
            event_note = note or f"Tracking {code}"
        elif target == S.DELIVERED:
            sub.delivered_at = now
        elif target == S.RETURN_REQUESTED:
            deadline = return_deadline(sub)
            if deadline is None or now > deadline:
                raise Conflict(
                    "The 7-day return window for this order has closed.",
                    code="return_window_closed",
                )
            text = " ".join((reason or "").split())
            if len(text) < 10:
                raise ValidationFailed(
                    "Tell the boutique what's wrong (at least 10 characters).",
                    code="reason_required",
                )
            sub.return_reason = text
            sub.return_requested_at = now
            event_note = text
        elif target == S.CANCELLED:
            event_note = " ".join((reason or note or "").split()) or None
            if actor == SE and not event_note:
                raise ValidationFailed(
                    "Tell the buyer why you're cancelling.", code="reason_required"
                )
        elif target == S.COMPLETED and current == S.RETURN_REQUESTED and not (note or "").strip():
            raise ValidationFailed("Explain why the return is declined.", code="reason_required")

        # Money and stock.
        if target in (S.CANCELLED, S.REFUNDED):
            if sub.subtotal_qc > 0:
                await ws.refund_escrow(
                    session,
                    order.buyer_id,
                    sub.subtotal_qc,
                    f"sub:{sub.id}:refund",
                    memo=f"Refund · {sub.number} · {seller.boutique_name}",
                    meta={"order_id": str(order.id), "sub_order_id": str(sub.id)},
                )
            await _restore_stock(session, sub)
            await _free_voucher(session, sub, order.buyer_id)
        elif target == S.COMPLETED:
            if sub.subtotal_qc > 0:
                await ws.release_escrow(
                    session,
                    seller.user_id,
                    sub.subtotal_qc,
                    f"sub:{sub.id}",
                    memo=f"Order {sub.number}",
                    meta={"order_id": str(order.id), "sub_order_id": str(sub.id)},
                )
            sub.escrow_released_at = now
            await award_points(session, buyer, sub.subtotal_qc // POINTS_PER_QC, sub)

        sub.status = target.value
        session.add(
            OrderStatusEvent(
                sub_order_id=sub.id,
                from_status=current.value,
                to_status=target.value,
                actor_id=user.id if user else None,
                note=event_note[:300] if event_note else None,
                created_at=now,
            )
        )
        await session.flush()
        statuses = list(
            (
                await session.scalars(select(SubOrder.status).where(SubOrder.order_id == order.id))
            ).all()
        )
        order.status = rollup(statuses)
        emails = _notify(
            session, settings, actor, current, target, sub, order, buyer, seller, event_note
        )
    log.info(
        "sub_order_transition",
        sub=sub.number,
        frm=current.value,
        to=target.value,
        actor=actor.value,
    )
    return Moved(sub, emails, changed=True)


async def _restore_stock(session: AsyncSession, sub: SubOrder) -> None:
    items = list(
        (await session.scalars(select(OrderItem).where(OrderItem.sub_order_id == sub.id))).all()
    )
    variants = {
        v.id: v
        for v in (
            await session.scalars(
                select(Variant)
                .where(Variant.id.in_([i.variant_id for i in items]))
                .order_by(Variant.id)
                .with_for_update()
            )
        ).all()
    }
    for item in items:
        if (v := variants.get(item.variant_id)) is not None:
            v.stock += item.qty
    await session.flush()
    for pid in {i.product_id for i in items}:
        product = await session.get(Product, pid)
        if product is None:
            continue
        rows = list((await session.scalars(select(Variant).where(Variant.product_id == pid))).all())
        refresh_denormalized(product, rows)


async def _free_voucher(session: AsyncSession, sub: SubOrder, buyer_id: uuid.UUID) -> None:
    """A cancelled or refunded sub-order gives the buyer their voucher back."""
    redemption = await session.scalar(
        select(VoucherRedemption).where(VoucherRedemption.sub_order_id == sub.id)
    )
    if redemption is None:
        return
    voucher = await session.scalar(
        select(Voucher).where(Voucher.id == redemption.voucher_id).with_for_update()
    )
    if voucher is not None and voucher.used_count > 0:
        voucher.used_count -= 1
    await session.delete(redemption)


async def award_points(session: AsyncSession, user: User, amount: int, sub: SubOrder) -> int:
    """Append to the Que Points ledger (once per sub-order) and update the cache."""
    if amount <= 0:
        return 0
    key = f"sub:{sub.id}:points"
    if await session.scalar(select(PointsEntry.id).where(PointsEntry.source_key == key)):
        return 0
    locked = await session.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert locked is not None
    locked.que_points += amount
    session.add(
        PointsEntry(
            user_id=locked.id,
            amount=amount,
            balance_after=locked.que_points,
            reason="order_completed",
            source_key=key,
            memo=f"Order {sub.number}",
        )
    )
    return amount


# ─── Notifications ─────────────────────────────────────────────────────────

_BUYER_COPY: dict[S, tuple[str, str, str]] = {
    # target: (subject, heading, body) — {n} sub-order number, {b} boutique
    S.PROCESSING: (
        "{b} is preparing {n}",
        "Your pieces are being prepared.",
        "{b} has started preparing order {n}.",
    ),
    S.SHIPPED: ("{n} has shipped", "On its way.", "{b} shipped order {n}. Tracking number: {t}."),
    S.DELIVERED: (
        "{n} was delivered",
        "Delivered.",
        "Order {n} from {b} was delivered. Tap Received if all is well, "
        "or request a return within 7 days.",
    ),
    S.CANCELLED: (
        "{n} was cancelled",
        "Order cancelled.",
        "Order {n} from {b} was cancelled and {q} is back in your QueWallet.",
    ),
    S.REFUNDED: (
        "Refund for {n}",
        "Your refund is in.",
        "{b} approved your return for {n}. {q} is back in your QueWallet.",
    ),
    S.COMPLETED: (
        "{n} is complete",
        "Thank you.",
        "Order {n} from {b} is complete. +{p} Que Points are in your account.",
    ),
}
#: Status emails for these; the rest are in-app only (no notification spam).
_EMAIL = {S.SHIPPED, S.DELIVERED, S.CANCELLED, S.REFUNDED}


def _notify(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    current: S,
    target: S,
    sub: SubOrder,
    order: Order,
    buyer: User,
    seller: SellerProfile,
    note: str | None,
) -> list[EmailLog]:
    emails: list[EmailLog] = []
    fmt = {
        "n": sub.number,
        "b": seller.boutique_name,
        "t": sub.tracking_no or "",
        "q": f"QC {sub.subtotal_qc:,}",
        "p": f"{sub.subtotal_qc // POINTS_PER_QC:,}",
    }
    path = f"/account/orders/{order.id}"
    if actor != B and target in _BUYER_COPY:
        subject, heading, body = (x.format(**fmt) for x in _BUYER_COPY[target])
        if target == S.COMPLETED and current == S.RETURN_REQUESTED:
            subject, heading = f"Return update for {sub.number}", "Return declined."
            body = f"{seller.boutique_name} declined the return for {sub.number}: {note}"
        if target == S.CANCELLED and note:
            body = f"{body} Reason: {note}"
        if target in _EMAIL or current == S.RETURN_REQUESTED:
            email = email_templates.order_update(
                template=f"order_{target.value.lower()}",
                name=buyer.name,
                subject=subject,
                heading=heading,
                body=body,
                url=f"{settings.frontend_url}{path}",
                inbox_path=path,
            )
            emails.append(
                email_service.queue(session, user=buyer, to_email=buyer.email, email=email)
            )
        else:
            session.add(
                Notification(
                    user_id=buyer.id,
                    type=f"order.{target.value.lower()}",
                    payload={"title": subject, "body": body, "action_url": path},
                )
            )
    # The boutique hears about what the buyer (or the clock) did.
    seller_copy: dict[S, tuple[str, str]] = {
        S.CANCELLED: (
            f"{sub.number} cancelled by the buyer",
            f"Reason: {note or 'none given'}. Stock was restored.",
        ),
        S.RETURN_REQUESTED: (f"Return requested for {sub.number}", f"Reason: {note}"),
        S.COMPLETED: (
            f"QC {sub.subtotal_qc - sub.commission_qc:,} released for {sub.number}",
            "Escrow released to your QueWallet (after the 5% commission).",
        ),
    }
    if (
        actor in (B, SY, AD)
        and target in seller_copy
        and not (target == S.CANCELLED and actor != B)
    ):
        title, body = seller_copy[target]
        session.add(
            Notification(
                user_id=seller.user_id,
                type=f"order.{target.value.lower()}",
                payload={"title": title, "body": body, "action_url": "/seller/orders"},
            )
        )
    return emails


# ─── Auto-release (7 days after delivery) ──────────────────────────────────


async def release_due(
    session: AsyncSession, settings: Settings, *, older_than: timedelta = AUTO_RELEASE_AFTER
) -> int:
    """Complete every DELIVERED sub-order delivered at least `older_than` ago.
    Run by the scheduler hourly; admins can fast-forward with `older_than=0`."""
    cutoff = utcnow() - older_than
    ids = list(
        (
            await session.scalars(
                select(SubOrder.id).where(
                    SubOrder.status == S.DELIVERED.value, SubOrder.delivered_at <= cutoff
                )
            )
        ).all()
    )
    done = 0
    for sub_id in ids:
        try:
            moved = await transition(session, settings, None, sub_id, S.COMPLETED.value)
            done += int(moved.changed)
        except Conflict:
            continue  # moved by someone else in the meantime (e.g. a return opened)
        except Exception:  # noqa: BLE001 — one bad row must not stop the batch
            log.exception("auto_release_failed", sub_order_id=str(sub_id))
    return done
