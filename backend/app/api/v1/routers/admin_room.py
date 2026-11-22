"""Admin Control Room (Phase 9): overview, sellers, users, catalog, featured
slots and moderation. Role-gated as a whole; each route also declares its
permission, and every mutation is audit-logged in the service."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import AppSettings, DbSession, client_ip, require_permission, require_role
from app.core.permissions import Permission, Role
from app.models.user import User
from app.schemas.common import ApiModel
from app.schemas.control import (
    AdminCategory,
    AdminCollection,
    AdminSellerPage,
    AdminUserDetail,
    AdminUserRow,
    CategoryPatch,
    CollectionIn,
    FlagGroup,
    ModerationAction,
    Overview,
    PickRow,
    ReasonIn,
    ReportAck,
    ReportIn,
    SellerStatus,
    SubcategoryIn,
    SubcategoryPatch,
    TagOption,
    ToggleIn,
)
from app.services import control_service as cs
from app.services.catalog_service import CatalogService

router = APIRouter(
    prefix="/admin", tags=["control room"], dependencies=[Depends(require_role(Role.ADMIN))]
)
reports_router = APIRouter(prefix="/reports", tags=["reports"])


def perm(p: Permission):  # type: ignore[no-untyped-def]
    return Depends(require_permission(p))


class UserPage(ApiModel):
    items: list[AdminUserRow]
    total: int


class CollectionsOut(ApiModel):
    items: list[AdminCollection]
    tags: list[TagOption]


@router.get("/overview", response_model=Overview, summary="GMV, orders, people, escrow")
async def overview(session: DbSession, admin: User = perm(Permission.ANALYTICS_VIEW)) -> Overview:
    return await cs.overview(session, admin)


# ─── Sellers ───────────────────────────────────────────────────────────────


@router.get("/sellers", response_model=AdminSellerPage, summary="Every boutique, by status")
async def sellers(
    session: DbSession,
    settings: AppSettings,
    status: SellerStatus | None = None,
    q: str | None = None,
    admin: User = perm(Permission.SELLER_APPROVE),
) -> AdminSellerPage:
    items, counts = await cs.sellers(session, settings, admin, status=status, q=q)
    return AdminSellerPage(items=items, counts=counts)


@router.post(
    "/sellers/{seller_id}/suspend",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Suspend a boutique",
)
async def suspend(
    seller_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    session: DbSession,
    admin: User = perm(Permission.SELLER_APPROVE),
) -> None:
    await cs.set_suspended(session, admin, seller_id, True, body.reason, client_ip(request))


@router.post(
    "/sellers/{seller_id}/reinstate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reinstate a boutique",
)
async def reinstate(
    seller_id: uuid.UUID,
    request: Request,
    session: DbSession,
    admin: User = perm(Permission.SELLER_APPROVE),
) -> None:
    await cs.set_suspended(session, admin, seller_id, False, None, client_ip(request))


@router.put(
    "/sellers/{seller_id}/featured",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Feature a boutique on the home page",
)
async def feature_boutique(
    seller_id: uuid.UUID,
    body: ToggleIn,
    request: Request,
    session: DbSession,
    admin: User = perm(Permission.CATALOG_MANAGE),
) -> None:
    await cs.set_boutique_featured(session, admin, seller_id, body.on, client_ip(request))


# ─── Users ─────────────────────────────────────────────────────────────────


@router.get("/users", response_model=UserPage, summary="Search people")
async def users(
    session: DbSession,
    q: str | None = None,
    role: Literal["BUYER", "SELLER", "ADMIN"] | None = None,
    status: Literal["active", "banned"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    admin: User = perm(Permission.USER_VIEW),
) -> UserPage:
    items, total = await cs.users(
        session, admin, q=q, role=role, status=status, limit=limit, offset=offset
    )
    return UserPage(items=items, total=total)


@router.get("/users/{user_id}", response_model=AdminUserDetail, summary="One person")
async def user_detail(
    user_id: uuid.UUID, session: DbSession, admin: User = perm(Permission.USER_VIEW)
) -> AdminUserDetail:
    return await cs.user_detail(session, admin, user_id)


# ─── Catalog ───────────────────────────────────────────────────────────────


@router.get(
    "/catalog/categories", response_model=list[AdminCategory], summary="Categories & subcategories"
)
async def categories(
    session: DbSession, admin: User = perm(Permission.CATALOG_MANAGE)
) -> list[AdminCategory]:
    return await cs.categories(session, admin)


@router.patch(
    "/catalog/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Edit a category",
)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryPatch,
    request: Request,
    session: DbSession,
    admin: User = perm(Permission.CATALOG_MANAGE),
) -> None:
    await cs.update_category(session, admin, category_id, body, client_ip(request))


@router.post(
    "/catalog/categories/{category_id}/subcategories",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
    summary="Add a subcategory",
)
async def create_subcategory(
    category_id: uuid.UUID,
    body: SubcategoryIn,
    request: Request,
    session: DbSession,
    admin: User = perm(Permission.CATALOG_MANAGE),
) -> None:
    await cs.create_subcategory(session, admin, category_id, body.name, client_ip(request))


@router.patch(
    "/catalog/subcategories/{sub_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Rename / reorder",
)
async def update_subcategory(
    sub_id: uuid.UUID,
    body: SubcategoryPatch,
    request: Request,
    session: DbSession,
    admin: User = perm(Permission.CATALOG_MANAGE),
) -> None:
    await cs.update_subcategory(session, admin, sub_id, body, client_ip(request))


@router.delete(
    "/catalog/subcategories/{sub_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an empty subcategory",
)
async def delete_subcategory(
    sub_id: uuid.UUID,
    request: Request,
    session: DbSession,
    admin: User = perm(Permission.CATALOG_MANAGE),
) -> None:
    await cs.delete_subcategory(session, admin, sub_id, client_ip(request))


@router.get(
    "/catalog/subcategories/{sub_id}/picks",
    response_model=list[PickRow],
    summary="Connoisseur's pick candidates",
)
async def picks(
    sub_id: uuid.UUID,
    session: DbSession,
    settings: AppSettings,
    admin: User = perm(Permission.CATALOG_MANAGE),
) -> list[PickRow]:
    return await cs.picks(session, settings, admin, sub_id)


@router.put(
    "/catalog/products/{product_id}/pick",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set the Connoisseur's pick",
)
async def set_pick(
    product_id: uuid.UUID,
    body: ToggleIn,
    request: Request,
    session: DbSession,
    admin: User = perm(Permission.CATALOG_MANAGE),
) -> None:
    await cs.set_pick(session, admin, product_id, body.on, client_ip(request))


@router.get("/catalog/collections", response_model=CollectionsOut, summary="Editorial collections")
async def collections(
    session: DbSession, settings: AppSettings, admin: User = perm(Permission.CATALOG_MANAGE)
) -> CollectionsOut:
    items, tags = await cs.collections(session, settings, admin)
    return CollectionsOut(items=items, tags=tags)


@router.post(
    "/catalog/collections",
    response_model=AdminCollection,
    status_code=status.HTTP_201_CREATED,
    summary="New collection",
)
async def create_collection(
    body: CollectionIn,
    request: Request,
    session: DbSession,
    settings: AppSettings,
    admin: User = perm(Permission.CATALOG_MANAGE),
) -> AdminCollection:
    c = await cs.save_collection(session, settings, admin, body, None, client_ip(request))
    return cs.collection_out(c, 0, CatalogService(session, settings).abs_url)


@router.put(
    "/catalog/collections/{collection_id}",
    response_model=AdminCollection,
    summary="Edit a collection",
)
async def update_collection(
    collection_id: uuid.UUID,
    body: CollectionIn,
    request: Request,
    session: DbSession,
    settings: AppSettings,
    admin: User = perm(Permission.CATALOG_MANAGE),
) -> AdminCollection:
    c = await cs.save_collection(session, settings, admin, body, collection_id, client_ip(request))
    return cs.collection_out(c, 0, CatalogService(session, settings).abs_url)


@router.delete(
    "/catalog/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a collection",
)
async def delete_collection(
    collection_id: uuid.UUID,
    request: Request,
    session: DbSession,
    admin: User = perm(Permission.CATALOG_MANAGE),
) -> None:
    await cs.delete_collection(session, admin, collection_id, client_ip(request))


# ─── Moderation ────────────────────────────────────────────────────────────


@router.get("/moderation", response_model=list[FlagGroup], summary="Reported products and reviews")
async def moderation(
    session: DbSession,
    settings: AppSettings,
    status: Literal["open", "resolved"] = "open",
    admin: User = perm(Permission.REVIEW_MODERATE),
) -> list[FlagGroup]:
    return await cs.flags(session, settings, admin, status=status)


@router.post(
    "/moderation/{target_type}/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dismiss reports, take content down, or restore it",
)
async def moderate(
    target_type: Literal["product", "review"],
    target_id: uuid.UUID,
    body: ModerationAction,
    request: Request,
    session: DbSession,
    admin: User = perm(Permission.REVIEW_MODERATE),
) -> None:
    await cs.moderate(
        session, admin, target_type, target_id, body.action, body.note, client_ip(request)
    )


# ─── Shopper reports ───────────────────────────────────────────────────────


@reports_router.post(
    "",
    response_model=ReportAck,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Report a product or review",
)
async def report(
    body: ReportIn,
    session: DbSession,
    user: User = Depends(require_permission(Permission.PROFILE_MANAGE)),
) -> ReportAck:
    await cs.report(session, user, body)
    return ReportAck(received=True)
