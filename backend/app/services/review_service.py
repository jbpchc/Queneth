"""Verified-purchase reviews: only the buyer of a delivered line can review it,
once. Photos are review uploads (Cloudinary, or the local fallback)."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound
from app.core.permissions import Permission, assert_can
from app.core.text import option_label
from app.models.catalog import Product, Review
from app.models.commerce import Order, OrderItem, OrderStatus, SubOrder
from app.models.user import User
from app.schemas.commerce import ReviewIn
from app.services.media_service import MediaService

REVIEWABLE = {OrderStatus.DELIVERED.value, OrderStatus.COMPLETED.value}


async def create(session: AsyncSession, settings: Settings, user: User, body: ReviewIn) -> Review:
    assert_can(user, Permission.REVIEW_WRITE)
    item = await session.get(OrderItem, body.order_item_id)
    sub = await session.get(SubOrder, item.sub_order_id) if item else None
    order = await session.get(Order, sub.order_id) if sub else None
    if item is None or sub is None or order is None or order.buyer_id != user.id:
        raise NotFound("We couldn't find that purchase.", code="order_item_not_found")
    if sub.status not in REVIEWABLE:
        raise Conflict("You can review a piece once it has been delivered.", code="not_delivered")
    if await session.scalar(select(Review.id).where(Review.order_item_id == item.id)):
        raise Conflict("You've already reviewed this piece.", code="already_reviewed")

    media = MediaService(session, settings)
    photos = []
    for asset_id in dict.fromkeys(body.photo_asset_ids):  # de-duplicated, order kept
        asset = await media.get_ready_asset(user, asset_id, "review")
        photos.append(media.to_out(asset).url)

    review = Review(
        product_id=item.product_id,
        buyer_id=user.id,
        order_item_id=item.id,
        rating=body.rating,
        fit=body.fit,
        title=body.title or None,
        body=body.body,
        photos=photos,
        variant_label=option_label(item.options_snapshot) or None,
        status="published",
    )
    session.add(review)
    try:
        await session.flush()
    except IntegrityError as exc:  # a concurrent duplicate
        await session.rollback()
        raise Conflict("You've already reviewed this piece.", code="already_reviewed") from exc
    await refresh_rating(session, item.product_id)
    await session.commit()
    return review


async def refresh_rating(session: AsyncSession, product_id) -> None:  # type: ignore[no-untyped-def]
    avg, count = (
        await session.execute(
            select(func.avg(Review.rating), func.count(Review.id)).where(
                Review.product_id == product_id, Review.status == "published"
            )
        )
    ).one()
    product = await session.get(Product, product_id)
    if product is not None:
        product.rating_avg = round(float(avg or 0), 2)
        product.rating_count = int(count or 0)
