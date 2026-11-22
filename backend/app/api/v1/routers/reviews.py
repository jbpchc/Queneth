"""Verified-purchase reviews."""

from fastapi import APIRouter, Depends, status

from app.api.deps import AppSettings, DbSession, require_permission
from app.core.permissions import Permission
from app.models.catalog import Product
from app.models.user import User
from app.schemas.commerce import ReviewCreated, ReviewIn
from app.services import review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post(
    "",
    response_model=ReviewCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Review a delivered piece (once per bought line)",
)
async def create_review(
    body: ReviewIn,
    session: DbSession,
    settings: AppSettings,
    user: User = Depends(require_permission(Permission.REVIEW_WRITE)),
) -> ReviewCreated:
    review = await review_service.create(session, settings, user, body)
    product = await session.get(Product, review.product_id)
    return ReviewCreated(
        id=review.id, product_slug=product.slug if product else "", rating=review.rating
    )
