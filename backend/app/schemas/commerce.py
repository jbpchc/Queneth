import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, field_validator

from app.schemas.catalog import Ref
from app.schemas.common import ApiModel


def normalize_ph_mobile(value: object) -> object:
    """Postel's Law: '0917 123 4567', '+63 917-123-4567', '9171234567' → '+639171234567'."""
    if not isinstance(value, str):
        return value
    digits = re.sub(r"\D", "", value)
    if digits.startswith("63") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10 or not digits.startswith("9"):
        raise ValueError("Enter a PH mobile number, e.g. 0917 123 4567.")
    return f"+63{digits}"


PhMobile = Annotated[str, BeforeValidator(normalize_ph_mobile)]


class AddressIn(ApiModel):
    label: str = Field(min_length=1, max_length=40, examples=["Home"])
    recipient: str = Field(min_length=2, max_length=120, examples=["Isabela Reyes"])
    phone: PhMobile = Field(examples=["0917 123 4567"])
    line1: str = Field(min_length=3, max_length=200, examples=["12 Magsaysay Ave., Unit 4B"])
    barangay_code: str = Field(pattern=r"^\d{9}$", examples=["051724003"])
    zip: str = Field(pattern=r"^\d{4}$", examples=["4400"])
    is_default: bool = False

    @field_validator("label", "recipient", "line1", mode="before")
    @classmethod
    def _squash(cls, v: object) -> object:
        return " ".join(v.split()) if isinstance(v, str) else v


class AddressOut(ApiModel):
    id: uuid.UUID
    label: str
    recipient: str
    phone: str
    line1: str
    barangay_code: str
    barangay: str
    city: str
    province: str | None
    region: str
    zip: str
    is_default: bool


class VoucherApply(ApiModel):
    code: str = Field(min_length=3, max_length=40, examples=["NOCTURNE15"])


class AppliedVoucher(ApiModel):
    id: uuid.UUID
    code: str
    description: str | None
    discount_qc: int
    #: Why it doesn't apply right now (e.g. below minimum spend); None when it does.
    problem: str | None


class BoardIn(ApiModel):
    name: str = Field(min_length=1, max_length=48, examples=["Wedding season"])

    @field_validator("name", mode="before")
    @classmethod
    def _squash(cls, v: object) -> object:
        return " ".join(v.split()) if isinstance(v, str) else v


class BoardOut(ApiModel):
    id: uuid.UUID
    name: str
    count: int


class MoveToBoard(ApiModel):
    board_id: uuid.UUID | None


class CheckoutRequest(ApiModel):
    address_id: uuid.UUID
    pin: str = Field(min_length=6, max_length=11)
    #: The total the buyer reviewed. If prices changed since, checkout stops (409).
    expected_total_qc: int = Field(ge=0)
    #: Pay for only these bag lines ("Buy now"); everything else stays in the bag.
    #: Omitted: the whole bag.
    item_ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=50)


class OrderItemOut(ApiModel):
    id: uuid.UUID
    title: str
    brand: str
    options: dict[str, str]
    image: str | None
    product_slug: str
    unit_price_qc: int
    qty: int
    line_total_qc: int
    #: Set once the buyer has reviewed this line (verified purchase).
    review_id: uuid.UUID | None
    can_review: bool


class StatusEventOut(ApiModel):
    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


class SubOrderOut(ApiModel):
    id: uuid.UUID
    number: str
    status: str
    boutique: Ref
    boutique_logo: str | None
    items_total_qc: int
    discount_qc: int
    subtotal_qc: int
    voucher_code: str | None
    tracking_no: str | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    escrow_released_at: datetime | None
    return_reason: str | None
    #: Last moment a return can be requested (delivered + 7 days).
    return_deadline: datetime | None
    #: Escrow auto-releases to the boutique at this time unless a return is opened.
    auto_release_at: datetime | None
    #: What the viewing buyer may do now: "cancel", "received", "return".
    actions: list[str]
    items: list[OrderItemOut]
    events: list[StatusEventOut]


class OrderOut(ApiModel):
    id: uuid.UUID
    number: str
    status: str
    subtotal_qc: int
    discount_qc: int
    total_qc: int
    points_pending: int
    points_earned: int
    shipping_address: dict[str, str | None]
    created_at: datetime
    sub_orders: list[SubOrderOut]


class OrderSummary(ApiModel):
    id: uuid.UUID
    number: str
    status: str
    total_qc: int
    item_count: int
    boutiques: list[str]
    preview_images: list[str]
    created_at: datetime


SubStatus = Literal[
    "PAID",
    "PROCESSING",
    "SHIPPED",
    "DELIVERED",
    "COMPLETED",
    "CANCELLED",
    "RETURN_REQUESTED",
    "REFUNDED",
]


class CancelRequest(ApiModel):
    reason: str | None = Field(default=None, max_length=300, examples=["Ordered the wrong size."])


class ReturnRequest(ApiModel):
    reason: str = Field(
        min_length=10, max_length=500, examples=["The silk has a pulled thread near the hem."]
    )


class TransitionRequest(ApiModel):
    """Seller/admin move. SHIPPED needs a tracking number; returns are approved
    with REFUNDED or declined with COMPLETED (a note is required to decline)."""

    to: SubStatus
    note: str | None = Field(default=None, max_length=300)
    tracking_no: str | None = Field(default=None, max_length=40, examples=["QNX-4821-7730"])


class SellerSubOrder(ApiModel):
    id: uuid.UUID
    number: str
    order_id: uuid.UUID
    status: str
    created_at: datetime
    buyer_name: str
    shipping_address: dict[str, str | None]
    items_total_qc: int
    discount_qc: int
    subtotal_qc: int
    commission_qc: int
    #: What the boutique receives when escrow releases (subtotal − 5 %).
    net_qc: int
    voucher_code: str | None
    tracking_no: str | None
    return_reason: str | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    auto_release_at: datetime | None
    #: Statuses this seller may move it to now.
    next: list[str]
    items: list[OrderItemOut]
    events: list[StatusEventOut]


class SellerQueue(ApiModel):
    items: list[SellerSubOrder]
    counts: dict[str, int]
    next_cursor: str | None = None
    has_more: bool = False


class ReleaseResult(ApiModel):
    released: int


class ReviewIn(ApiModel):
    order_item_id: uuid.UUID
    rating: int = Field(ge=1, le=5)
    fit: Literal["small", "true", "large"] | None = None
    title: str | None = Field(default=None, max_length=120)
    body: str = Field(min_length=10, max_length=2000)
    photo_asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=4)

    @field_validator("title", "body", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class ReviewCreated(ApiModel):
    id: uuid.UUID
    product_slug: str
    rating: int
