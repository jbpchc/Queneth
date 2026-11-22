"""Catalog: boutiques, taxonomy, products, variants, reviews, editorial."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, TZDateTime

if TYPE_CHECKING:
    from app.models.user import User


class SellerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A boutique. Owned by one user who holds the SELLER role."""

    __tablename__ = "seller_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    boutique_name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    tagline: Mapped[str | None] = mapped_column(String(160))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    banner_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str | None] = mapped_column(Text)
    return_policy: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(String(320))
    city: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Shown to the applicant when an application is rejected (Phase 9 UI).
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    #: Storefront settings: up to 4 pinned products and a 6-image lookbook.
    featured_product_ids: Mapped[list[str]] = mapped_column(JSONType, default=list)
    lookbook: Mapped[list[dict[str, str]]] = mapped_column(JSONType, default=list)
    #: The "Your first sale" banner shows until the seller dismisses it.
    first_sale_seen_at: Mapped[datetime | None] = mapped_column(TZDateTime())

    user: Mapped["User"] = relationship(back_populates="seller_profile", foreign_keys=[user_id])


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(48))
    slug: Mapped[str] = mapped_column(String(48), unique=True)
    tagline: Mapped[str | None] = mapped_column(String(160))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    #: JSON Schema of the category's typed attributes (generated from Pydantic).
    attribute_schema: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

    subcategories: Mapped[list["Subcategory"]] = relationship(
        back_populates="category", order_by="Subcategory.sort_order", lazy="selectin"
    )


class Subcategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subcategories"
    __table_args__ = (
        UniqueConstraint("category_id", "slug", name="uq_subcategories_category_slug"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(48))
    slug: Mapped[str] = mapped_column(String(48))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped[Category] = relationship(back_populates="subcategories")


class Brand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Fictional houses only (spec §2)."""

    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80), unique=True)


class Product(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A listing. Prices, stock, sizes and colors are denormalized from the
    variants (see product_service.refresh_denormalized) so listings and facets
    never need to load variants."""

    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_status_category", "status", "category_id"),
        Index("ix_products_published_at", "published_at"),
        CheckConstraint("min_price_qc >= 0", name="price_non_negative"),
    )

    seller_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seller_profiles.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"), index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), index=True)
    subcategory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subcategories.id"), index=True)
    title: Mapped[str] = mapped_column(String(140))
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str] = mapped_column(Text)
    condition: Mapped[str] = mapped_column(String(24), default="new")
    authenticity_note: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSONType, default=list)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    #: Visible from this moment (scheduled drops publish in the future).
    published_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    is_connoisseur_pick: Mapped[bool] = mapped_column(Boolean, default=False)
    curated_score: Mapped[int] = mapped_column(Integer, default=0)

    # Denormalized for listings, facets and sorting.
    min_price_qc: Mapped[int] = mapped_column(Integer, default=0)
    max_price_qc: Mapped[int] = mapped_column(Integer, default=0)
    compare_at_qc: Mapped[int | None] = mapped_column(Integer)
    total_stock: Mapped[int] = mapped_column(Integer, default=0)
    sizes: Mapped[list[str]] = mapped_column(JSONType, default=list)
    colors: Mapped[list[str]] = mapped_column(JSONType, default=list)
    facet_values: Mapped[dict[str, list[str]]] = mapped_column(JSONType, default=dict)
    search_text: Mapped[str] = mapped_column(Text, default="")
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    wishlist_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    #: Conversion funnel (views → wishlists → bag adds → orders), spec §10.
    bag_add_count: Mapped[int] = mapped_column(Integer, default=0)

    seller: Mapped[SellerProfile] = relationship(lazy="joined")
    brand: Mapped[Brand] = relationship(lazy="joined")
    category: Mapped[Category] = relationship(lazy="joined")
    subcategory: Mapped[Subcategory] = relationship(lazy="joined")
    images: Mapped[list["ProductImage"]] = relationship(
        order_by="ProductImage.position", lazy="selectin", cascade="all, delete-orphan"
    )
    variants: Mapped[list["Variant"]] = relationship(
        order_by="Variant.position", lazy="raise", cascade="all, delete-orphan"
    )


class ProductImage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_images"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(500))
    alt: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)
    #: Links a color swatch to the image it shows (Uniform Connectedness).
    color: Mapped[str | None] = mapped_column(String(32))


class Variant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "variants"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="stock_non_negative"),
        CheckConstraint("price_qc > 0", name="price_positive"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    #: e.g. {"size": "M", "color": "Ivory"} or {"volume": "50 ml"}
    options: Mapped[dict[str, str]] = mapped_column(JSONType, default=dict)
    price_qc: Mapped[int] = mapped_column(Integer)
    compare_at_qc: Mapped[int | None] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=3)
    position: Mapped[int] = mapped_column(Integer, default=0)


class Review(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Verified-purchase reviews. Writing them arrives with orders (Phase 7);
    the seed adds demo reviews so product pages show real summaries."""

    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: Verified purchase: one review per bought line (unique; NULL for seeded reviews).
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("order_items.id", ondelete="SET NULL"), unique=True
    )
    rating: Mapped[int] = mapped_column(Integer)
    fit: Mapped[str | None] = mapped_column(String(8))  # small | true | large
    title: Mapped[str | None] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    photos: Mapped[list[str]] = mapped_column(JSONType, default=list)
    variant_label: Mapped[str | None] = mapped_column(String(80))
    seller_reply: Mapped[str | None] = mapped_column(Text)
    seller_replied_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    status: Mapped[str] = mapped_column(String(16), default="published")
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)

    buyer: Mapped["User"] = relationship(lazy="joined")


class Follow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("buyer_id", "seller_id", name="uq_follows_buyer_seller"),)

    buyer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seller_profiles.id", ondelete="CASCADE"), index=True
    )


class Collection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Editorial edit, built by admins from tagged products."""

    __tablename__ = "collections"

    title: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    kicker: Mapped[str | None] = mapped_column(String(60))
    subtitle: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    tag: Mapped[str] = mapped_column(String(48), index=True)
    hero_url: Mapped[str | None] = mapped_column(String(500))
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


drop_products = Table(
    "drop_products",
    Base.metadata,
    Column("drop_id", ForeignKey("drops.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
)


class Drop(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A scheduled release. Its products publish at `starts_at`, so countdowns
    are always real (no fake urgency)."""

    __tablename__ = "drops"
    __table_args__ = (Index("ix_drops_pending_notify", "notified_at", "starts_at"),)

    seller_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seller_profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    hero_url: Mapped[str | None] = mapped_column(String(500))
    starts_at: Mapped[datetime] = mapped_column(TZDateTime(), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    #: Set when "Notify me" subscribers were told the drop is live.
    notified_at: Mapped[datetime | None] = mapped_column(TZDateTime())

    seller: Mapped[SellerProfile] = relationship(lazy="joined")
    products: Mapped[list[Product]] = relationship(secondary=drop_products, lazy="selectin")


class DropSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """ "Notify me" on a drop (opt-in; notified when it goes live)."""

    __tablename__ = "drop_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "drop_id", name="uq_drop_subscriptions_user_drop"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    drop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("drops.id", ondelete="CASCADE"), index=True
    )
    notified_at: Mapped[datetime | None] = mapped_column(TZDateTime())


class WishlistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Saved product, optionally filed on a named board."""

    __tablename__ = "wishlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_wishlist_items_user_product"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wishlist_boards.id", ondelete="SET NULL"), index=True
    )
    #: Price when saved, for "price dropped" indicators.
    saved_price_qc: Mapped[int | None] = mapped_column(Integer)


class CartItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("user_id", "variant_id", name="uq_cart_items_user_variant"),
        CheckConstraint("qty BETWEEN 1 AND 10", name="qty_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"), index=True
    )
    qty: Mapped[int] = mapped_column(Integer, default=1)
    saved_for_later: Mapped[bool] = mapped_column(Boolean, default=False)
