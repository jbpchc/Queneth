import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.catalog import BoutiqueCard, ProductCard
from app.schemas.commerce import AppliedVoucher, BoardOut
from app.schemas.common import ApiModel


class WishlistEntry(ApiModel):
    product: ProductCard
    saved_at: datetime
    saved_price_qc: int | None
    price_dropped: bool
    available: bool
    board_id: uuid.UUID | None


class WishlistOut(ApiModel):
    items: list[WishlistEntry]
    count: int
    boards: list[BoardOut]


class WishlistIds(ApiModel):
    product_ids: list[uuid.UUID]


class SaveResult(ApiModel):
    saved: bool
    wishlist_count: int


class BagItem(ApiModel):
    id: uuid.UUID
    qty: int
    variant_id: uuid.UUID
    options: dict[str, str]
    unit_price_qc: int
    compare_at_qc: int | None
    line_total_qc: int
    stock: int
    available: bool
    product: ProductCard


class BagGroup(ApiModel):
    """UX: Common Region — the bag is grouped by boutique (each ships separately)."""

    boutique: BoutiqueCard
    items: list[BagItem]
    subtotal_qc: int
    #: The boutique's voucher applied to this group (one per boutique).
    voucher: AppliedVoucher | None
    discount_qc: int
    total_qc: int


class BagOut(ApiModel):
    groups: list[BagGroup]
    #: "Save for later" items: kept out of the total until moved back.
    saved: list[BagItem]
    item_count: int
    subtotal_qc: int
    discount_qc: int
    total_qc: int


class SaveForLater(ApiModel):
    saved: bool


class AddToBag(ApiModel):
    variant_id: uuid.UUID
    qty: int = Field(default=1, ge=1, le=10)
    #: "Buy now": set the line to exactly `qty` (instead of adding to what's
    #: there) so checkout of just this line buys what the shopper chose.
    buy_now: bool = False


class SetQty(ApiModel):
    qty: int = Field(ge=1, le=10)
