"""Seller Studio (Phase 8): application, dashboard, products, inventory, drops,
vouchers, reviews, earnings and storefront settings. The fulfilment queue lives
in `seller.py` (Phase 7). Every route re-checks ownership in its service."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, status

from app.api.deps import AppSettings, CurrentUser, DbSession, require_permission
from app.core.errors import NotFound
from app.core.permissions import Permission
from app.models.catalog import SellerProfile
from app.models.user import User
from app.schemas.catalog import ReviewOut
from app.schemas.studio import (
    BoutiqueSettingsIn,
    BoutiqueSettingsOut,
    BulkIds,
    BulkResult,
    Dashboard,
    DropIn,
    Earnings,
    InventoryBulk,
    InventoryRow,
    ProductBasics,
    ProductPatch,
    ReplyIn,
    SellerApplicationIn,
    SellerApplicationOut,
    StudioDrop,
    StudioMeta,
    StudioProduct,
    StudioProductPage,
    StudioReview,
    StudioVoucher,
    VoucherIn,
    VoucherPatch,
)
from app.services import boutique_service, studio_service
from app.services import studio_product_service as sps
from app.services.catalog_service import CatalogService, review_out

application_router = APIRouter(prefix="/seller-application", tags=["seller application"])
router = APIRouter(prefix="/seller", tags=["seller studio"])

Seller = Depends(require_permission(Permission.PRODUCT_CREATE))
Inventory = Depends(require_permission(Permission.INVENTORY_MANAGE))
Drops = Depends(require_permission(Permission.DROP_MANAGE))
Vouchers = Depends(require_permission(Permission.VOUCHER_MANAGE))
Reviews = Depends(require_permission(Permission.REVIEW_REPLY))
Earner = Depends(require_permission(Permission.EARNINGS_VIEW))


# ─── Application ───────────────────────────────────────────────────────────


@application_router.get(
    "", response_model=SellerApplicationOut | None, summary="Your boutique application, if any"
)
async def my_application(
    session: DbSession, settings: AppSettings, user: CurrentUser
) -> SellerApplicationOut | None:
    profile = await boutique_service.mine(session, user)
    if profile is None:
        return None
    return boutique_service.application_out(profile, CatalogService(session, settings).abs_url)


@application_router.put(
    "",
    response_model=SellerApplicationOut,
    summary="Apply to sell (or update / resubmit your application)",
)
async def apply(
    body: SellerApplicationIn, session: DbSession, settings: AppSettings, user: CurrentUser
) -> SellerApplicationOut:
    profile = await boutique_service.apply(session, settings, user, body)
    return boutique_service.application_out(profile, CatalogService(session, settings).abs_url)


# ─── Dashboard & settings ──────────────────────────────────────────────────


@router.get("/dashboard", response_model=Dashboard, summary="Today, the last 30 days, and alerts")
async def dashboard(session: DbSession, settings: AppSettings, user: User = Earner) -> Dashboard:
    return await studio_service.dashboard(session, settings, user)


@router.post(
    "/first-sale/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hide the first-sale celebration",
)
async def dismiss_first_sale(session: DbSession, user: User = Earner) -> None:
    await boutique_service.dismiss_first_sale(session, user)


@router.get("/settings", response_model=BoutiqueSettingsOut, summary="Storefront settings")
async def get_settings_(
    session: DbSession, settings: AppSettings, user: User = Seller
) -> BoutiqueSettingsOut:
    profile = await session.get(SellerProfile, boutique_service.own_boutique(user))
    if profile is None:
        raise NotFound("We couldn't find your boutique.", code="boutique_not_found")
    return boutique_service.settings_out(profile, CatalogService(session, settings).abs_url)


@router.put("/settings", response_model=BoutiqueSettingsOut, summary="Update storefront settings")
async def put_settings(
    body: BoutiqueSettingsIn, session: DbSession, settings: AppSettings, user: User = Seller
) -> BoutiqueSettingsOut:
    profile = await boutique_service.update_settings(session, settings, user, body)
    return boutique_service.settings_out(profile, CatalogService(session, settings).abs_url)


@router.get("/earnings", response_model=Earnings, summary="Available, in escrow, payouts")
async def earnings(session: DbSession, user: User = Earner) -> Earnings:
    return await studio_service.earnings(session, user)


# ─── Products ──────────────────────────────────────────────────────────────


@router.get("/products/meta", response_model=StudioMeta, summary="Categories, axes, brands")
async def product_meta(session: DbSession, user: User = Seller) -> StudioMeta:
    return await sps.meta(session, user)


@router.get("/products", response_model=StudioProductPage, summary="Your products")
async def products(
    session: DbSession,
    settings: AppSettings,
    status: Literal["draft", "active", "archived"] | None = None,
    q: str | None = None,
    user: User = Seller,
) -> StudioProductPage:
    items, counts = await sps.rows(session, settings, user, status=status, q=q)
    return StudioProductPage(items=items, counts=counts)


@router.post(
    "/products",
    response_model=StudioProduct,
    status_code=status.HTTP_201_CREATED,
    summary="Start a product (wizard step 1 creates the draft)",
)
async def create_product(
    body: ProductBasics, session: DbSession, settings: AppSettings, user: User = Seller
) -> StudioProduct:
    p = await sps.create(session, user, body)
    return await sps.to_out(session, settings, p)


@router.get("/products/{product_id}", response_model=StudioProduct, summary="One product")
async def get_product(
    product_id: uuid.UUID, session: DbSession, settings: AppSettings, user: User = Seller
) -> StudioProduct:
    return await sps.to_out(session, settings, await sps.get(session, user, product_id))


@router.patch(
    "/products/{product_id}", response_model=StudioProduct, summary="Autosave any wizard step"
)
async def patch_product(
    product_id: uuid.UUID,
    body: ProductPatch,
    session: DbSession,
    settings: AppSettings,
    user: User = Seller,
) -> StudioProduct:
    p = await sps.patch(session, settings, user, product_id, body)
    return await sps.to_out(session, settings, p)


@router.post(
    "/products/{product_id}/publish", response_model=StudioProduct, summary="Publish a draft"
)
async def publish(
    product_id: uuid.UUID, session: DbSession, settings: AppSettings, user: User = Seller
) -> StudioProduct:
    p = await sps.publish(session, user, product_id)
    return await sps.to_out(session, settings, p)


@router.post(
    "/products/{product_id}/duplicate",
    response_model=StudioProduct,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate as a new draft",
)
async def duplicate(
    product_id: uuid.UUID, session: DbSession, settings: AppSettings, user: User = Seller
) -> StudioProduct:
    p = await sps.duplicate(session, user, product_id)
    return await sps.to_out(session, settings, p)


@router.delete(
    "/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a draft"
)
async def delete_draft(product_id: uuid.UUID, session: DbSession, user: User = Seller) -> None:
    await sps.delete_draft(session, user, product_id)


@router.post("/products/archive", response_model=BulkResult, summary="Archive (bulk)")
async def archive(body: BulkIds, session: DbSession, user: User = Seller) -> BulkResult:
    return BulkResult(updated=await sps.set_archived(session, user, body.ids, True))


@router.post("/products/restore", response_model=BulkResult, summary="Restore archived (bulk)")
async def restore(body: BulkIds, session: DbSession, user: User = Seller) -> BulkResult:
    return BulkResult(updated=await sps.set_archived(session, user, body.ids, False))


# ─── Inventory ─────────────────────────────────────────────────────────────


@router.get("/inventory", response_model=list[InventoryRow], summary="Every variant's stock")
async def inventory(
    session: DbSession, settings: AppSettings, low: bool = False, user: User = Inventory
) -> list[InventoryRow]:
    return await sps.inventory(session, settings, user, low_only=low)


@router.patch("/inventory", response_model=BulkResult, summary="Update stock / thresholds")
async def update_inventory(
    body: InventoryBulk, session: DbSession, user: User = Inventory
) -> BulkResult:
    return BulkResult(updated=await sps.update_inventory(session, user, body.updates))


# ─── Drops ─────────────────────────────────────────────────────────────────


@router.get("/drops", response_model=list[StudioDrop], summary="Your drops")
async def drops(session: DbSession, settings: AppSettings, user: User = Drops) -> list[StudioDrop]:
    return [
        await studio_service.drop_out(session, settings, d)
        for d in await studio_service.drops(session, user)
    ]


@router.post(
    "/drops", response_model=StudioDrop, status_code=status.HTTP_201_CREATED, summary="Schedule"
)
async def create_drop(
    body: DropIn, session: DbSession, settings: AppSettings, user: User = Drops
) -> StudioDrop:
    d = await studio_service.save_drop(session, settings, user, body)
    return await studio_service.drop_out(session, settings, d)


@router.put("/drops/{drop_id}", response_model=StudioDrop, summary="Edit a scheduled drop")
async def update_drop(
    drop_id: uuid.UUID, body: DropIn, session: DbSession, settings: AppSettings, user: User = Drops
) -> StudioDrop:
    d = await studio_service.save_drop(session, settings, user, body, drop_id)
    return await studio_service.drop_out(session, settings, d)


@router.delete(
    "/drops/{drop_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Cancel a scheduled drop"
)
async def delete_drop(drop_id: uuid.UUID, session: DbSession, user: User = Drops) -> None:
    await studio_service.delete_drop(session, user, drop_id)


# ─── Vouchers ──────────────────────────────────────────────────────────────


@router.get("/vouchers", response_model=list[StudioVoucher], summary="Your vouchers")
async def vouchers(session: DbSession, user: User = Vouchers) -> list[StudioVoucher]:
    return await studio_service.vouchers(session, user)


@router.post(
    "/vouchers",
    response_model=StudioVoucher,
    status_code=status.HTTP_201_CREATED,
    summary="Create a voucher (seller-funded)",
)
async def create_voucher(
    body: VoucherIn, session: DbSession, user: User = Vouchers
) -> StudioVoucher:
    return studio_service.voucher_out(await studio_service.create_voucher(session, user, body))


@router.patch("/vouchers/{voucher_id}", response_model=StudioVoucher, summary="Pause / edit")
async def update_voucher(
    voucher_id: uuid.UUID, body: VoucherPatch, session: DbSession, user: User = Vouchers
) -> StudioVoucher:
    v = await studio_service.update_voucher(session, user, voucher_id, body)
    return studio_service.voucher_out(v)


@router.delete(
    "/vouchers/{voucher_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an unused voucher",
)
async def delete_voucher(voucher_id: uuid.UUID, session: DbSession, user: User = Vouchers) -> None:
    await studio_service.delete_voucher(session, user, voucher_id)


# ─── Reviews ───────────────────────────────────────────────────────────────


@router.get("/reviews", response_model=list[StudioReview], summary="Reviews of your pieces")
async def reviews(
    session: DbSession, unreplied: bool = False, user: User = Reviews
) -> list[StudioReview]:
    return await studio_service.reviews(session, user, unreplied=unreplied)


@router.put("/reviews/{review_id}/reply", response_model=ReviewOut, summary="Reply (or edit reply)")
async def reply(
    review_id: uuid.UUID, body: ReplyIn, session: DbSession, user: User = Reviews
) -> ReviewOut:
    return review_out(await studio_service.reply(session, user, review_id, body.reply))
