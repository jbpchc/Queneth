"""Promotions: admin campaigns, seller enrollment, public deals."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.catalog import ProductCard
from app.schemas.common import ApiModel

PromotionState = Literal["upcoming", "live", "ended", "cancelled"]


def _squash(v: object) -> object:
    return " ".join(v.split()) if isinstance(v, str) else v


class PromotionIn(ApiModel):
    title: str = Field(min_length=3, max_length=120, examples=["End of the Year Sale"])
    badge: str = Field(min_length=2, max_length=32, examples=["Year-End Sale"])
    description: str | None = Field(default=None, max_length=1000)
    starts_at: datetime
    ends_at: datetime
    min_discount_percent: int = Field(default=5, ge=1, le=90)
    max_discount_percent: int = Field(default=70, ge=1, le=90)
    hero_asset_id: uuid.UUID | None = None

    _clean = field_validator("title", "badge", mode="before")(_squash)

    @model_validator(mode="after")
    def _valid(self) -> "PromotionIn":
        if self.ends_at <= self.starts_at:
            raise ValueError("The promotion must end after it starts.")
        if self.min_discount_percent > self.max_discount_percent:
            raise ValueError("The minimum discount can't be above the maximum.")
        return self


class PromotionOut(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    badge: str
    description: str | None
    hero_url: str | None
    starts_at: datetime
    ends_at: datetime
    min_discount_percent: int
    max_discount_percent: int
    is_active: bool
    state: PromotionState
    #: Pieces enrolled (not withdrawn) and boutiques taking part.
    product_count: int
    seller_count: int


class PromotionCard(PromotionOut):
    """A campaign as shoppers see it: only pieces actually on sale now."""

    preview: list[ProductCard]
    top_discount_percent: int


class PromotionDetail(PromotionCard):
    products: list[ProductCard]


class DealsOut(ApiModel):
    promotions: list[PromotionCard]
    #: Every live piece with a genuine markdown, biggest discount first.
    on_sale: list[ProductCard]


class EnrollIn(ApiModel):
    product_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    discount_percent: int = Field(ge=1, le=90)


class SellerEntry(ApiModel):
    id: uuid.UUID
    promotion_id: uuid.UUID
    promotion_title: str
    promotion_state: PromotionState
    product_id: uuid.UUID
    product_title: str
    image: str | None
    discount_percent: int
    status: Literal["scheduled", "live", "ended", "withdrawn"]
    #: Current lowest price and what it will be / is during the sale.
    price_qc: int
    sale_price_qc: int


class SellerPromotions(ApiModel):
    open: list[PromotionOut]
    entries: list[SellerEntry]
