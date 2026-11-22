"""Wishlist boards ("Wedding season", "Signature scents"). Owner-scoped."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.core.permissions import Permission, assert_can
from app.models.catalog import WishlistItem
from app.models.commerce import WishlistBoard
from app.models.user import User
from app.schemas.commerce import BoardOut

MAX_BOARDS = 20


async def list_for(session: AsyncSession, user: User) -> list[BoardOut]:
    assert_can(user, Permission.WISHLIST_MANAGE)
    rows = (
        await session.execute(
            select(WishlistBoard, func.count(WishlistItem.id))
            .outerjoin(WishlistItem, WishlistItem.board_id == WishlistBoard.id)
            .where(WishlistBoard.user_id == user.id)
            .group_by(WishlistBoard.id)
            .order_by(WishlistBoard.created_at)
        )
    ).all()
    return [BoardOut(id=b.id, name=b.name, count=n) for b, n in rows]


async def _owned(session: AsyncSession, user: User, board_id: uuid.UUID) -> WishlistBoard:
    board = await session.get(WishlistBoard, board_id)
    if board is None or board.user_id != user.id:
        raise NotFound("We couldn't find that board.", code="board_not_found")
    return board


async def _name_taken(
    session: AsyncSession, user: User, name: str, exclude: uuid.UUID | None
) -> bool:
    stmt = select(WishlistBoard.id).where(
        WishlistBoard.user_id == user.id, func.lower(WishlistBoard.name) == name.lower()
    )
    if exclude:
        stmt = stmt.where(WishlistBoard.id != exclude)
    return (await session.scalar(stmt)) is not None


async def create(session: AsyncSession, user: User, name: str) -> WishlistBoard:
    assert_can(user, Permission.WISHLIST_MANAGE)
    count = await session.scalar(select(func.count()).where(WishlistBoard.user_id == user.id)) or 0
    if count >= MAX_BOARDS:
        raise Conflict(f"You can have up to {MAX_BOARDS} boards.", code="board_limit")
    if await _name_taken(session, user, name, None):
        raise Conflict("You already have a board with that name.", code="board_exists")
    board = WishlistBoard(user_id=user.id, name=name)
    session.add(board)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("You already have a board with that name.", code="board_exists") from exc
    return board


async def rename(
    session: AsyncSession, user: User, board_id: uuid.UUID, name: str
) -> WishlistBoard:
    assert_can(user, Permission.WISHLIST_MANAGE)
    board = await _owned(session, user, board_id)
    if await _name_taken(session, user, name, board.id):
        raise Conflict("You already have a board with that name.", code="board_exists")
    board.name = name
    await session.commit()
    return board


async def delete(session: AsyncSession, user: User, board_id: uuid.UUID) -> None:
    """Deleting a board keeps its pieces saved (they move to "All saved")."""
    assert_can(user, Permission.WISHLIST_MANAGE)
    board = await _owned(session, user, board_id)
    items = await session.scalars(select(WishlistItem).where(WishlistItem.board_id == board.id))
    for item in items.all():
        item.board_id = None
    await session.delete(board)
    await session.commit()


async def move(
    session: AsyncSession, user: User, product_id: uuid.UUID, board_id: uuid.UUID | None
) -> None:
    assert_can(user, Permission.WISHLIST_MANAGE)
    item = await session.scalar(
        select(WishlistItem).where(
            WishlistItem.user_id == user.id, WishlistItem.product_id == product_id
        )
    )
    if item is None:
        raise NotFound("That piece isn't in your wishlist.", code="wishlist_item_not_found")
    if board_id is not None:
        await _owned(session, user, board_id)
    item.board_id = board_id
    await session.commit()
