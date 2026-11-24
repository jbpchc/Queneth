import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AppSettings, DbSession, require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.commerce import BoardIn, BoardOut, MoveToBoard, VoucherApply
from app.schemas.shop import (
    AddToBag,
    BagOut,
    SaveForLater,
    SaveResult,
    SetQty,
    WishlistIds,
    WishlistOut,
)
from app.services import board_service, shop_service, voucher_service
from app.services.catalog_service import CatalogService

wishlist_router = APIRouter(prefix="/wishlist", tags=["wishlist"])
cart_router = APIRouter(prefix="/cart", tags=["cart"])

Shopper = Depends(require_permission(Permission.WISHLIST_MANAGE))
BagUser = Depends(require_permission(Permission.CART_MANAGE))


@wishlist_router.get("", response_model=WishlistOut, summary="Saved pieces")
async def wishlist(session: DbSession, settings: AppSettings, user: User = Shopper) -> WishlistOut:
    return await shop_service.wishlist(session, CatalogService(session, settings), user)


@wishlist_router.get(
    "/ids", response_model=WishlistIds, summary="Saved product ids (for heart state)"
)
async def wishlist_ids(session: DbSession, user: User = Shopper) -> WishlistIds:
    return WishlistIds(product_ids=await shop_service.wishlist_ids(session, user))


@wishlist_router.put("/{product_id}", response_model=SaveResult, summary="Save a piece")
async def save(product_id: uuid.UUID, session: DbSession, user: User = Shopper) -> SaveResult:
    return SaveResult(saved=True, wishlist_count=await shop_service.save(session, user, product_id))


@wishlist_router.delete(
    "/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a piece"
)
async def unsave(product_id: uuid.UUID, session: DbSession, user: User = Shopper) -> None:
    await shop_service.unsave(session, user, product_id)


@cart_router.get("", response_model=BagOut, summary="Your bag, grouped by boutique")
async def get_bag(
    session: DbSession,
    settings: AppSettings,
    user: User = BagUser,
    items: list[uuid.UUID] | None = Query(
        default=None, max_length=50, description='Only these lines (the "Buy now" checkout)'
    ),
) -> BagOut:
    return await shop_service.bag(session, CatalogService(session, settings), user, items)


@cart_router.post(
    "/items", response_model=BagOut, status_code=status.HTTP_201_CREATED, summary="Add to bag"
)
async def add(
    body: AddToBag, session: DbSession, settings: AppSettings, user: User = BagUser
) -> BagOut:
    await shop_service.add_to_bag(session, user, body.variant_id, body.qty, buy_now=body.buy_now)
    return await shop_service.bag(session, CatalogService(session, settings), user)


@cart_router.patch("/items/{item_id}", response_model=BagOut, summary="Change quantity")
async def set_qty(
    item_id: uuid.UUID,
    body: SetQty,
    session: DbSession,
    settings: AppSettings,
    user: User = BagUser,
) -> BagOut:
    await shop_service.set_qty(session, user, item_id, body.qty)
    return await shop_service.bag(session, CatalogService(session, settings), user)


@cart_router.delete("/items/{item_id}", response_model=BagOut, summary="Remove from bag")
async def remove(
    item_id: uuid.UUID, session: DbSession, settings: AppSettings, user: User = BagUser
) -> BagOut:
    await shop_service.remove_from_bag(session, user, item_id)
    return await shop_service.bag(session, CatalogService(session, settings), user)


@cart_router.put(
    "/items/{item_id}/saved", response_model=BagOut, summary="Save for later / move back to bag"
)
async def save_for_later(
    item_id: uuid.UUID,
    body: SaveForLater,
    session: DbSession,
    settings: AppSettings,
    user: User = BagUser,
) -> BagOut:
    await shop_service.set_saved_for_later(session, user, item_id, body.saved)
    return await shop_service.bag(session, CatalogService(session, settings), user)


@cart_router.post("/vouchers", response_model=BagOut, summary="Apply a boutique voucher")
async def apply_voucher(
    body: VoucherApply, session: DbSession, settings: AppSettings, user: User = BagUser
) -> BagOut:
    await voucher_service.apply(session, user, body.code)
    return await shop_service.bag(session, CatalogService(session, settings), user)


@cart_router.delete("/vouchers/{voucher_id}", response_model=BagOut, summary="Remove a voucher")
async def remove_voucher(
    voucher_id: uuid.UUID, session: DbSession, settings: AppSettings, user: User = BagUser
) -> BagOut:
    await voucher_service.remove(session, user, voucher_id)
    return await shop_service.bag(session, CatalogService(session, settings), user)


# ─── Wishlist boards ───────────────────────────────────────────────────────


@wishlist_router.get("/boards", response_model=list[BoardOut], summary="Your boards")
async def boards(session: DbSession, user: User = Shopper) -> list[BoardOut]:
    return await board_service.list_for(session, user)


@wishlist_router.post(
    "/boards", response_model=BoardOut, status_code=status.HTTP_201_CREATED, summary="New board"
)
async def create_board(body: BoardIn, session: DbSession, user: User = Shopper) -> BoardOut:
    board = await board_service.create(session, user, body.name)
    return BoardOut(id=board.id, name=board.name, count=0)


@wishlist_router.patch("/boards/{board_id}", response_model=BoardOut, summary="Rename a board")
async def rename_board(
    board_id: uuid.UUID, body: BoardIn, session: DbSession, user: User = Shopper
) -> BoardOut:
    await board_service.rename(session, user, board_id, body.name)
    return next(b for b in await board_service.list_for(session, user) if b.id == board_id)


@wishlist_router.delete(
    "/boards/{board_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a board (its pieces stay saved)",
)
async def delete_board(board_id: uuid.UUID, session: DbSession, user: User = Shopper) -> None:
    await board_service.delete(session, user, board_id)


@wishlist_router.put(
    "/{product_id}/board",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="File a saved piece on a board (null = no board)",
)
async def move_to_board(
    product_id: uuid.UUID, body: MoveToBoard, session: DbSession, user: User = Shopper
) -> None:
    await board_service.move(session, user, product_id, body.board_id)
