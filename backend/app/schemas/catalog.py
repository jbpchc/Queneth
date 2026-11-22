import uuid
from datetime import datetime
from typing import Any, Literal

from app.schemas.common import ApiModel

Badge = Literal["new_drop", "low_stock", "sold_out", "sale", "preloved", "connoisseur_pick"]
SortKey = Literal["curated", "newest", "price_asc", "price_desc", "most_wished", "top_rated"]


class Ref(ApiModel):
    name: str
    slug: str


class ImageOut(ApiModel):
    url: str
    alt: str
    color: str | None = None


class Swatch(ApiModel):
    name: str
    hex: str | None


class ProductCard(ApiModel):
    """What a product card needs — and nothing more (Prägnanz)."""

    id: uuid.UUID
    slug: str
    title: str
    brand: Ref
    boutique: Ref
    category: str
    subcategory: str
    price_qc: int
    max_price_qc: int
    compare_at_qc: int | None
    image: ImageOut | None
    hover_image: ImageOut | None
    colors: list[Swatch]
    sizes: list[str]
    rating_avg: float
    rating_count: int
    condition: str
    total_stock: int
    badges: list[Badge]


class FacetValue(ApiModel):
    value: str
    label: str
    count: int
    hex: str | None = None


class PriceRange(ApiModel):
    min: int
    max: int


class Facets(ApiModel):
    subcategories: list[FacetValue]
    brands: list[FacetValue]
    boutiques: list[FacetValue]
    sizes: list[FacetValue]
    colors: list[FacetValue]
    conditions: list[FacetValue]
    price: PriceRange
    #: Category-specific facets, e.g. {"notes": [...], "concentration": [...]}.
    extra: dict[str, list[FacetValue]]


class ProductListing(ApiModel):
    items: list[ProductCard]
    next_cursor: str | None
    has_more: bool
    total: int
    facets: Facets
    #: UX: Choice Overload — one highlighted pick per listing.
    connoisseur_pick_id: uuid.UUID | None


class VariantOut(ApiModel):
    id: uuid.UUID
    sku: str
    options: dict[str, str]
    price_qc: int
    compare_at_qc: int | None
    stock: int
    low_stock: bool


class BoutiqueCard(ApiModel):
    id: uuid.UUID
    name: str
    slug: str
    tagline: str | None
    city: str | None
    logo_url: str | None
    banner_url: str | None
    follower_count: int
    product_count: int = 0
    is_following: bool = False


class BoutiqueDetail(BoutiqueCard):
    bio: str | None
    return_policy: str | None
    rating_avg: float
    rating_count: int
    since: datetime | None
    #: Pinned by the seller in Studio settings (up to 4, published only).
    featured: list["ProductCard"]
    lookbook: list[ImageOut]


class ReviewOut(ApiModel):
    id: uuid.UUID
    author: str
    rating: int
    fit: Literal["small", "true", "large"] | None
    title: str | None
    body: str
    photos: list[str]
    variant_label: str | None
    seller_reply: str | None
    helpful_count: int
    verified: bool
    created_at: datetime


class ReviewSummary(ApiModel):
    average: float
    count: int
    distribution: dict[str, int]
    #: Share of fit votes; None when there are no fit votes (non-apparel).
    fit: dict[str, int] | None
    fit_verdict: Literal["runs_small", "true_to_size", "runs_large"] | None


class DropRef(ApiModel):
    slug: str
    title: str
    starts_at: datetime
    ends_at: datetime | None


class ProductDetail(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    brand: Ref
    category: Ref
    subcategory: Ref
    description: str
    condition: str
    authenticity_note: str | None
    attributes: dict[str, Any]
    tags: list[str]
    images: list[ImageOut]
    variants: list[VariantOut]
    variant_axes: list[str]
    price_qc: int
    max_price_qc: int
    compare_at_qc: int | None
    total_stock: int
    colors: list[Swatch]
    sizes: list[str]
    badges: list[Badge]
    boutique: BoutiqueCard
    review_summary: ReviewSummary
    reviews: list[ReviewOut]
    drop: DropRef | None
    published_at: datetime | None
    you_may_also_love: list[ProductCard]
    complete_the_look: list[ProductCard]
    similar_scents: list[ProductCard]


class SubcategoryOut(ApiModel):
    name: str
    slug: str
    product_count: int


class CategoryOut(ApiModel):
    name: str
    slug: str
    tagline: str | None
    product_count: int
    cover_url: str
    subcategories: list[SubcategoryOut]


class CollectionOut(ApiModel):
    title: str
    slug: str
    kicker: str | None
    subtitle: str | None
    body: str | None
    tag: str
    hero_url: str | None
    product_count: int
    preview: list[ProductCard] = []


class DropOut(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    description: str | None
    hero_url: str | None
    starts_at: datetime
    ends_at: datetime | None
    status: Literal["upcoming", "live", "ended"]
    boutique: Ref
    product_count: int
    #: Products only appear once the drop is live (no early peeks).
    products: list[ProductCard]
    is_subscribed: bool = False


class HomeOut(ApiModel):
    live_drop: DropOut | None
    upcoming_drop: DropOut | None
    categories: list[CategoryOut]
    curated: list[ProductCard]
    trending: list[ProductCard]
    new_arrivals: list[ProductCard]
    featured_boutiques: list[BoutiqueCard]
    editorial: CollectionOut | None


class Suggestion(ApiModel):
    products: list[ProductCard]
    brands: list[Ref]
    boutiques: list[BoutiqueCard]
    categories: list[Ref]
    #: Did-you-mean when the query had no direct hit (typo tolerance).
    corrected: str | None


class FollowState(ApiModel):
    is_following: bool
    follower_count: int


class SubscriptionState(ApiModel):
    is_subscribed: bool
