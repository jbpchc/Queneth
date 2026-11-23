"""Seller Studio request/response models (Phase 8)."""

import re
import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.catalog import ImageOut, ReviewOut
from app.schemas.common import ApiModel


def _squash(v: object) -> object:
    return " ".join(v.split()) if isinstance(v, str) else v


# ─── Application & boutique settings ───────────────────────────────────────


class SellerApplicationIn(ApiModel):
    boutique_name: str = Field(min_length=3, max_length=60, examples=["Atelier Mira"])
    tagline: str | None = Field(default=None, max_length=160)
    bio: str = Field(min_length=40, max_length=2000)
    return_policy: str = Field(min_length=20, max_length=2000)
    contact_email: EmailStr
    city: str = Field(min_length=2, max_length=80)
    logo_asset_id: uuid.UUID | None = None
    banner_asset_id: uuid.UUID | None = None

    _clean = field_validator("boutique_name", "tagline", "city", mode="before")(_squash)


class SellerApplicationOut(ApiModel):
    id: uuid.UUID
    boutique_name: str
    slug: str
    tagline: str | None
    bio: str | None
    return_policy: str | None
    contact_email: str | None
    city: str | None
    logo_url: str | None
    banner_url: str | None
    status: Literal["pending", "approved", "rejected", "suspended"]
    rejection_reason: str | None
    created_at: datetime


class LookbookImage(ApiModel):
    url: str
    caption: str | None = None


class LookbookIn(ApiModel):
    """Either a newly uploaded asset or an image already in the lookbook."""

    asset_id: uuid.UUID | None = None
    url: str | None = None
    caption: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _one_source(self) -> "LookbookIn":
        if not (self.asset_id or self.url):
            raise ValueError("Each lookbook image needs an upload or an existing URL.")
        return self


class BoutiqueSettingsIn(ApiModel):
    tagline: str | None = Field(default=None, max_length=160)
    bio: str = Field(min_length=40, max_length=2000)
    return_policy: str = Field(min_length=20, max_length=2000)
    contact_email: EmailStr
    city: str = Field(min_length=2, max_length=80)
    logo_asset_id: uuid.UUID | None = None
    banner_asset_id: uuid.UUID | None = None
    featured_product_ids: list[uuid.UUID] = Field(default_factory=list, max_length=4)
    lookbook: list[LookbookIn] = Field(default_factory=list, max_length=6)

    _clean = field_validator("tagline", "city", mode="before")(_squash)


class BoutiqueSettingsOut(SellerApplicationOut):
    featured_product_ids: list[uuid.UUID]
    lookbook: list[LookbookImage]


class Decision(ApiModel):
    reason: str | None = Field(default=None, max_length=500)


# ─── Products ──────────────────────────────────────────────────────────────

#: "removed" = taken down by moderation; only an admin can restore it.
ProductStatus = Literal["draft", "active", "archived", "removed"]


class VariantIn(ApiModel):
    id: uuid.UUID | None = None
    options: dict[str, str] = Field(min_length=1)
    price_qc: int = Field(gt=0, le=10_000_000)
    compare_at_qc: int | None = Field(default=None, gt=0, le=10_000_000)
    stock: int = Field(ge=0, le=9999)
    low_stock_threshold: int = Field(default=3, ge=0, le=999)

    @field_validator("options", mode="before")
    @classmethod
    def _clean_options(cls, v: object) -> object:
        if not isinstance(v, dict):
            return v
        out = {str(k).strip().lower(): " ".join(str(val).split()) for k, val in v.items()}
        return {k: val for k, val in out.items() if k and val}

    @model_validator(mode="after")
    def _real_markdown(self) -> "VariantIn":
        # Spec §9: compare-at only for genuine markdowns.
        if self.compare_at_qc is not None and self.compare_at_qc <= self.price_qc:
            raise ValueError("The original price must be higher than the selling price.")
        return self


class ImageIn(ApiModel):
    asset_id: uuid.UUID | None = None
    url: str | None = None
    alt: str = Field(min_length=3, max_length=200)
    color: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def _one_source(self) -> "ImageIn":
        if not (self.asset_id or self.url):
            raise ValueError("Each image needs an upload or an existing URL.")
        return self


class ProductBasics(ApiModel):
    title: str = Field(min_length=3, max_length=120)
    #: Sellers are brands: leave empty to sell under your boutique's own name,
    #: or name a label you carry (multi-label boutiques).
    brand: str | None = Field(default=None, max_length=60)
    category: str = Field(examples=["perfumes"])
    subcategory: str = Field(examples=["eau-de-parfum"])
    condition: Literal["new", "pre-loved", "vintage"] = "new"

    _clean = field_validator("title", "brand", mode="before")(_squash)


class ProductPatch(ApiModel):
    """Autosave: every field optional; send only what changed."""

    title: str | None = Field(default=None, min_length=3, max_length=120)
    brand: str | None = Field(default=None, min_length=2, max_length=60)
    category: str | None = None
    subcategory: str | None = None
    condition: Literal["new", "pre-loved", "vintage"] | None = None
    description: str | None = Field(default=None, max_length=5000)
    authenticity_note: str | None = Field(default=None, max_length=1000)
    tags: list[str] | None = Field(default=None, max_length=12)
    attributes: dict[str, Any] | None = None
    images: list[ImageIn] | None = Field(default=None, max_length=10)
    variants: list[VariantIn] | None = Field(default=None, max_length=40)

    _clean = field_validator("title", "brand", mode="before")(_squash)

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, v: object) -> object:
        if not isinstance(v, list):
            return v
        seen: list[str] = []
        for t in v:
            t = re.sub(r"[^a-z0-9-]+", "-", str(t).strip().lower()).strip("-")
            if t and t not in seen:
                seen.append(t)
        return seen


class StudioVariant(ApiModel):
    id: uuid.UUID
    sku: str
    options: dict[str, str]
    price_qc: int
    compare_at_qc: int | None
    stock: int
    low_stock_threshold: int
    sold: int


class StudioProduct(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    brand: str
    category: str
    subcategory: str
    condition: str
    description: str
    authenticity_note: str | None
    tags: list[str]
    attributes: dict[str, Any]
    status: ProductStatus
    published_at: datetime | None
    #: Set when the product is waiting for a scheduled drop.
    scheduled_drop: str | None
    images: list[ImageOut]
    variants: list[StudioVariant]
    variant_axes: list[str]
    #: What still blocks publishing, e.g. ["Add at least one photo"]. Empty = ready.
    missing: list[str]
    updated_at: datetime


class StudioProductRow(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    category: str
    status: ProductStatus
    image: str | None
    min_price_qc: int
    total_stock: int
    variant_count: int
    low_stock: bool
    view_count: int
    wishlist_count: int
    sold: int
    updated_at: datetime


class StudioProductPage(ApiModel):
    items: list[StudioProductRow]
    counts: dict[str, int]


class BulkIds(ApiModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class BulkResult(ApiModel):
    updated: int


class CategoryOption(ApiModel):
    slug: str
    name: str
    subcategories: list[dict[str, str]]
    variant_axes: list[str]
    attribute_schema: dict[str, Any]


class StudioMeta(ApiModel):
    categories: list[CategoryOption]
    brands: list[str]


# ─── Inventory ─────────────────────────────────────────────────────────────


class InventoryRow(ApiModel):
    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_title: str
    product_status: ProductStatus
    image: str | None
    sku: str
    options: dict[str, str]
    price_qc: int
    stock: int
    low_stock_threshold: int
    low_stock: bool


class InventoryUpdate(ApiModel):
    variant_id: uuid.UUID
    stock: int | None = Field(default=None, ge=0, le=9999)
    low_stock_threshold: int | None = Field(default=None, ge=0, le=999)


class InventoryBulk(ApiModel):
    updates: list[InventoryUpdate] = Field(min_length=1, max_length=200)


# ─── Dashboard & earnings ──────────────────────────────────────────────────


class DayPoint(ApiModel):
    day: date
    revenue_qc: int
    orders: int


class TopProduct(ApiModel):
    id: uuid.UUID
    title: str
    image: str | None
    units: int
    revenue_qc: int


class Funnel(ApiModel):
    views: int
    wishlists: int
    bag_adds: int
    orders: int


class LowStock(ApiModel):
    variant_id: uuid.UUID
    product_id: uuid.UUID
    title: str
    options: dict[str, str]
    stock: int
    threshold: int


class Dashboard(ApiModel):
    boutique: str
    today_revenue_qc: int
    today_orders: int
    to_fulfil: int
    returns_open: int
    revenue_30d_qc: int
    series: list[DayPoint]
    funnel: Funnel
    top_products: list[TopProduct]
    low_stock: list[LowStock]
    #: True once, until dismissed: the first-sale celebration banner.
    first_sale: bool
    product_count: int


class Payout(ApiModel):
    reference: str
    amount_qc: int
    created_at: datetime


class Earnings(ApiModel):
    available_qc: int
    in_escrow_qc: int
    released_qc: int
    commission_paid_qc: int
    withdrawn_qc: int
    payouts: list[Payout]
    has_pin: bool


# ─── Drops ─────────────────────────────────────────────────────────────────


class DropIn(ApiModel):
    title: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    starts_at: datetime
    ends_at: datetime | None = None
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=24)
    hero_asset_id: uuid.UUID | None = None

    _clean = field_validator("title", mode="before")(_squash)

    @model_validator(mode="after")
    def _window(self) -> "DropIn":
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("The drop must end after it starts.")
        return self


class StudioDrop(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    description: str | None
    hero_url: str | None
    starts_at: datetime
    ends_at: datetime | None
    state: Literal["scheduled", "live", "ended"]
    product_ids: list[uuid.UUID]
    products: list[str]
    subscribers: int


# ─── Vouchers ──────────────────────────────────────────────────────────────


class VoucherIn(ApiModel):
    code: str = Field(min_length=4, max_length=24, examples=["MIRA15"])
    type: Literal["percent", "fixed"]
    value: int = Field(gt=0)
    min_spend_qc: int = Field(default=0, ge=0, le=10_000_000)
    max_uses: int = Field(default=100, ge=1, le=100_000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    description: str | None = Field(default=None, max_length=160)

    @field_validator("code", mode="before")
    @classmethod
    def _code(cls, v: object) -> object:
        # Postel's Law: " mira 15 " → "MIRA15".
        return "".join(v.split()).upper() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _valid(self) -> "VoucherIn":
        if not re.fullmatch(r"[A-Z0-9-]{4,24}", self.code):
            raise ValueError("Codes use letters, digits and dashes (4–24).")
        if self.type == "percent" and not 1 <= self.value <= 90:
            raise ValueError("Percent vouchers are between 1% and 90%.")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("The voucher must end after it starts.")
        return self


class VoucherPatch(ApiModel):
    is_active: bool | None = None
    max_uses: int | None = Field(default=None, ge=1, le=100_000)
    ends_at: datetime | None = None
    description: str | None = Field(default=None, max_length=160)


class StudioVoucher(ApiModel):
    id: uuid.UUID
    code: str
    type: str
    value: int
    min_spend_qc: int
    max_uses: int
    used_count: int
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    description: str | None
    state: Literal["active", "scheduled", "expired", "paused", "used_up"]
    discount_given_qc: int


# ─── Reviews ───────────────────────────────────────────────────────────────


class StudioReview(ReviewOut):
    product_id: uuid.UUID
    product_title: str
    product_slug: str


class ReplyIn(ApiModel):
    reply: str = Field(min_length=2, max_length=1000)
