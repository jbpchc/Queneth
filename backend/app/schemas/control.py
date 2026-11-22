"""Admin Control Room models (Phase 9)."""

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.schemas.admin import AdminUserOut
from app.schemas.common import ApiModel
from app.schemas.studio import DayPoint

# ─── Overview ──────────────────────────────────────────────────────────────


class CategoryShare(ApiModel):
    slug: str
    name: str
    revenue_qc: int
    units: int


class Overview(ApiModel):
    gmv_qc: int
    gmv_30d_qc: int
    orders: int
    orders_30d: int
    users_total: int
    active_buyers_30d: int
    sellers_active: int
    sellers_pending: int
    escrow_qc: int
    platform_revenue_qc: int
    open_reports: int
    series: list[DayPoint]
    top_categories: list[CategoryShare]


# ─── Sellers ───────────────────────────────────────────────────────────────

SellerStatus = Literal["pending", "approved", "rejected", "suspended"]


class Owner(ApiModel):
    id: uuid.UUID
    name: str
    email: str


class AdminSeller(ApiModel):
    id: uuid.UUID
    boutique_name: str
    slug: str
    status: SellerStatus
    owner: Owner
    city: str | None
    tagline: str | None
    bio: str | None
    logo_url: str | None
    product_count: int
    orders: int
    gmv_qc: int
    follower_count: int
    is_featured: bool
    rejection_reason: str | None
    created_at: datetime
    approved_at: datetime | None


class AdminSellerPage(ApiModel):
    items: list[AdminSeller]
    counts: dict[str, int]


class ReasonIn(ApiModel):
    reason: str = Field(min_length=5, max_length=500)


class ToggleIn(ApiModel):
    on: bool


# ─── Users ─────────────────────────────────────────────────────────────────


class Boutique(ApiModel):
    name: str
    slug: str
    status: str


class AdminUserRow(AdminUserOut):
    orders: int
    wallet_qc: int
    boutique: Boutique | None


class AdminUserDetail(AdminUserRow):
    spent_qc: int
    reviews: int
    reports_made: int
    recent_audit: list[dict[str, Any]]


# ─── Catalog ───────────────────────────────────────────────────────────────


class AdminSubcategory(ApiModel):
    id: uuid.UUID
    slug: str
    name: str
    sort_order: int
    product_count: int


class AdminCategory(ApiModel):
    id: uuid.UUID
    slug: str
    name: str
    tagline: str | None
    sort_order: int
    product_count: int
    attribute_schema: dict[str, Any]
    subcategories: list[AdminSubcategory]


class CategoryPatch(ApiModel):
    name: str | None = Field(default=None, min_length=2, max_length=48)
    tagline: str | None = Field(default=None, max_length=160)
    sort_order: int | None = Field(default=None, ge=0, le=100)


class SubcategoryIn(ApiModel):
    name: str = Field(min_length=2, max_length=48)

    @field_validator("name", mode="before")
    @classmethod
    def _squash(cls, v: object) -> object:
        return " ".join(v.split()) if isinstance(v, str) else v


class SubcategoryPatch(ApiModel):
    name: str | None = Field(default=None, min_length=2, max_length=48)
    sort_order: int | None = Field(default=None, ge=0, le=100)


class PickRow(ApiModel):
    id: uuid.UUID
    title: str
    slug: str
    boutique: str
    image: str | None
    price_qc: int
    is_pick: bool


class AdminCollection(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    kicker: str | None
    subtitle: str | None
    body: str | None
    tag: str
    hero_url: str | None
    is_featured: bool
    sort_order: int
    product_count: int


class CollectionIn(ApiModel):
    title: str = Field(min_length=3, max_length=120)
    kicker: str | None = Field(default=None, max_length=60)
    subtitle: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=4000)
    tag: str = Field(min_length=2, max_length=48, description="Products tagged with this appear.")
    is_featured: bool = False
    sort_order: int = Field(default=0, ge=0, le=100)
    hero_asset_id: uuid.UUID | None = None

    @field_validator("tag", mode="before")
    @classmethod
    def _tag(cls, v: object) -> object:
        return (
            re.sub(r"[^a-z0-9-]+", "-", v.strip().lower()).strip("-") if isinstance(v, str) else v
        )


class TagOption(ApiModel):
    tag: str
    products: int


# ─── Moderation ────────────────────────────────────────────────────────────

ReportReason = Literal["counterfeit", "offensive", "misleading", "spam", "other"]


class ReportIn(ApiModel):
    target_type: Literal["product", "review"]
    target_id: uuid.UUID
    reason: ReportReason
    note: str | None = Field(default=None, max_length=500)


class ReportAck(ApiModel):
    received: bool


class FlagGroup(ApiModel):
    target_type: Literal["product", "review"]
    target_id: uuid.UUID
    title: str
    subtitle: str
    excerpt: str | None
    url: str | None
    image: str | None
    #: The content's current state: product status or review status.
    content_status: str
    reports: int
    reasons: dict[str, int]
    notes: list[str]
    first_reported_at: datetime
    last_reported_at: datetime
    status: Literal["open", "resolved"]
    resolution: str | None


class ModerationAction(ApiModel):
    """dismiss = keep it up; hide/remove = take it down; restore = put it back."""

    action: Literal["dismiss", "hide", "remove", "restore"]
    note: str | None = Field(default=None, max_length=500)
