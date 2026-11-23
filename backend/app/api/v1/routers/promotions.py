"""Deals and promotions: the public deals feed, seller enrollment and admin
campaigns. Ownership and permissions are re-checked in the service."""

import uuid

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import AppSettings, DbSession, client_ip, require_permission, require_role
from app.core.permissions import Permission, Role
from app.models.user import User
from app.schemas.promotions import (
    DealsOut,
    EnrollIn,
    PromotionDetail,
    PromotionIn,
    PromotionOut,
    SellerPromotions,
)
from app.services import promotion_service as ps
from app.services.catalog_service import CatalogService

public_router = APIRouter(prefix="/catalog", tags=["deals"])
seller_router = APIRouter(prefix="/seller/promotions", tags=["seller studio"])
admin_router = APIRouter(
    prefix="/admin/promotions",
    tags=["control room"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)

Seller = Depends(require_permission(Permission.PRODUCT_UPDATE))
Admin = Depends(require_permission(Permission.CATALOG_MANAGE))


@public_router.get("/deals", response_model=DealsOut, summary="Live sales and marked-down pieces")
async def deals(session: DbSession, settings: AppSettings, response: Response) -> DealsOut:
    response.headers["Cache-Control"] = "public, max-age=30"
    return await ps.deals(session, settings)


@public_router.get(
    "/promotions/{slug}", response_model=PromotionDetail, summary="One live sale and its pieces"
)
async def promotion(slug: str, session: DbSession, settings: AppSettings) -> PromotionDetail:
    return await ps.detail(session, settings, slug)


# ─── Sellers ───────────────────────────────────────────────────────────────


@seller_router.get("", response_model=SellerPromotions, summary="Open sales and your entries")
async def seller_promotions(
    session: DbSession, settings: AppSettings, user: User = Seller
) -> SellerPromotions:
    return await ps.for_seller(session, settings, user)


@seller_router.post(
    "/{promotion_id}/entries",
    response_model=SellerPromotions,
    summary="Put pieces in a sale at a discount",
)
async def enroll(
    promotion_id: uuid.UUID,
    body: EnrollIn,
    session: DbSession,
    settings: AppSettings,
    user: User = Seller,
) -> SellerPromotions:
    await ps.enroll(session, user, promotion_id, body)
    return await ps.for_seller(session, settings, user)


@seller_router.delete(
    "/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Take a piece out of a sale (its price is restored)",
)
async def withdraw(entry_id: uuid.UUID, session: DbSession, user: User = Seller) -> None:
    await ps.withdraw(session, user, entry_id)


# ─── Admins ────────────────────────────────────────────────────────────────


@admin_router.get("", response_model=list[PromotionOut], summary="Every campaign")
async def list_promotions(
    session: DbSession, settings: AppSettings, admin: User = Admin
) -> list[PromotionOut]:
    return await ps.list_all(session, settings, admin)


async def _out(session: DbSession, settings: AppSettings, p) -> PromotionOut:  # type: ignore[no-untyped-def]
    return ps.promotion_out(p, CatalogService(session, settings).abs_url)


@admin_router.post(
    "", response_model=PromotionOut, status_code=status.HTTP_201_CREATED, summary="New campaign"
)
async def create_promotion(
    body: PromotionIn,
    request: Request,
    session: DbSession,
    settings: AppSettings,
    admin: User = Admin,
) -> PromotionOut:
    p = await ps.save(session, settings, admin, body, None, client_ip(request))
    return await _out(session, settings, p)


@admin_router.put("/{promotion_id}", response_model=PromotionOut, summary="Edit a campaign")
async def update_promotion(
    promotion_id: uuid.UUID,
    body: PromotionIn,
    request: Request,
    session: DbSession,
    settings: AppSettings,
    admin: User = Admin,
) -> PromotionOut:
    p = await ps.save(session, settings, admin, body, promotion_id, client_ip(request))
    return await _out(session, settings, p)


@admin_router.post(
    "/{promotion_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Call a campaign off (live prices are restored)",
)
async def cancel_promotion(
    promotion_id: uuid.UUID, request: Request, session: DbSession, admin: User = Admin
) -> None:
    await ps.cancel(session, admin, promotion_id, client_ip(request))
