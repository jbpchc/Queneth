"""Catalog: boutiques, taxonomy, products, variants, images, reviews, follows,
collections, drops, wishlist and cart.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), nullable=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
    ]


def _fk(table: str, column: str, ref: str, ondelete: str | None = None) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{ref}.id"], ondelete=ondelete, name=f"fk_{table}_{column}_{ref}"
    )


def _ix(table: str, *cols: str) -> None:
    op.create_index(f"ix_{table}_{'_'.join(cols)}", table, list(cols))


def upgrade() -> None:
    op.create_table(
        "seller_profiles",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("boutique_name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("tagline", sa.String(160)),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("banner_url", sa.String(500)),
        sa.Column("bio", sa.Text()),
        sa.Column("return_policy", sa.Text()),
        sa.Column("contact_email", sa.String(320)),
        sa.Column("city", sa.String(80)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("approved_by", sa.Uuid()),
        sa.Column("approved_at", TS),
        sa.Column("follower_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_seller_profiles"),
        sa.UniqueConstraint("user_id", name="uq_seller_profiles_user_id"),
        sa.UniqueConstraint("slug", name="uq_seller_profiles_slug"),
        _fk("seller_profiles", "user_id", "users", "CASCADE"),
        _fk("seller_profiles", "approved_by", "users", "SET NULL"),
    )
    _ix("seller_profiles", "status")

    op.create_table(
        "categories",
        _id(),
        sa.Column("name", sa.String(48), nullable=False),
        sa.Column("slug", sa.String(48), nullable=False),
        sa.Column("tagline", sa.String(160)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attribute_schema", pg.JSONB(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )
    op.create_table(
        "subcategories",
        _id(),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(48), nullable=False),
        sa.Column("slug", sa.String(48), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_subcategories"),
        sa.UniqueConstraint("category_id", "slug", name="uq_subcategories_category_slug"),
        _fk("subcategories", "category_id", "categories", "CASCADE"),
    )
    _ix("subcategories", "category_id")

    op.create_table(
        "brands",
        _id(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_brands"),
        sa.UniqueConstraint("slug", name="uq_brands_slug"),
    )

    op.create_table(
        "products",
        _id(),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("subcategory_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(140), nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("condition", sa.String(24), nullable=False),
        sa.Column("authenticity_note", sa.Text()),
        sa.Column("attributes", pg.JSONB(), nullable=False),
        sa.Column("tags", pg.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("published_at", TS),
        sa.Column("is_connoisseur_pick", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("curated_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_price_qc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_price_qc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("compare_at_qc", sa.Integer()),
        sa.Column("total_stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sizes", pg.JSONB(), nullable=False),
        sa.Column("colors", pg.JSONB(), nullable=False),
        sa.Column("facet_values", pg.JSONB(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("rating_avg", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wishlist_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", TS),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("slug", name="uq_products_slug"),
        sa.CheckConstraint("min_price_qc >= 0", name="ck_products_price_non_negative"),
        _fk("products", "seller_id", "seller_profiles", "CASCADE"),
        _fk("products", "brand_id", "brands"),
        _fk("products", "category_id", "categories"),
        _fk("products", "subcategory_id", "subcategories"),
    )
    for col in ("seller_id", "brand_id", "category_id", "subcategory_id", "published_at"):
        _ix("products", col)
    op.create_index("ix_products_status_category", "products", ["status", "category_id"])
    # Typo-tolerant search (spec §9): trigram GIN index over title, brand, notes, tags.
    op.execute(
        "CREATE INDEX ix_products_search_trgm ON products USING gin (search_text gin_trgm_ops)"
    )

    op.create_table(
        "product_images",
        _id(),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("alt", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("color", sa.String(32)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_product_images"),
        _fk("product_images", "product_id", "products", "CASCADE"),
    )
    _ix("product_images", "product_id")

    op.create_table(
        "variants",
        _id(),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("options", pg.JSONB(), nullable=False),
        sa.Column("price_qc", sa.Integer(), nullable=False),
        sa.Column("compare_at_qc", sa.Integer()),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_variants"),
        sa.UniqueConstraint("sku", name="uq_variants_sku"),
        sa.CheckConstraint("stock >= 0", name="ck_variants_stock_non_negative"),
        sa.CheckConstraint("price_qc > 0", name="ck_variants_price_positive"),
        _fk("variants", "product_id", "products", "CASCADE"),
    )
    _ix("variants", "product_id")
    _ix("variants", "sku")

    op.create_table(
        "reviews",
        _id(),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("order_item_id", sa.Uuid()),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("fit", sa.String(8)),
        sa.Column("title", sa.String(120)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("photos", pg.JSONB(), nullable=False),
        sa.Column("variant_label", sa.String(80)),
        sa.Column("seller_reply", sa.Text()),
        sa.Column("seller_replied_at", TS),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_reviews"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating_range"),
        _fk("reviews", "product_id", "products", "CASCADE"),
        _fk("reviews", "buyer_id", "users", "CASCADE"),
    )
    for col in ("product_id", "buyer_id", "order_item_id"):
        _ix("reviews", col)

    op.create_table(
        "follows",
        _id(),
        sa.Column("buyer_id", sa.Uuid(), nullable=False),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_follows"),
        sa.UniqueConstraint("buyer_id", "seller_id", name="uq_follows_buyer_seller"),
        _fk("follows", "buyer_id", "users", "CASCADE"),
        _fk("follows", "seller_id", "seller_profiles", "CASCADE"),
    )
    _ix("follows", "buyer_id")
    _ix("follows", "seller_id")

    op.create_table(
        "collections",
        _id(),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("kicker", sa.String(60)),
        sa.Column("subtitle", sa.String(200)),
        sa.Column("body", sa.Text()),
        sa.Column("tag", sa.String(48), nullable=False),
        sa.Column("hero_url", sa.String(500)),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_collections"),
        sa.UniqueConstraint("slug", name="uq_collections_slug"),
    )
    _ix("collections", "tag")

    op.create_table(
        "drops",
        _id(),
        sa.Column("seller_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("hero_url", sa.String(500)),
        sa.Column("starts_at", TS, nullable=False),
        sa.Column("ends_at", TS),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_drops"),
        sa.UniqueConstraint("slug", name="uq_drops_slug"),
        _fk("drops", "seller_id", "seller_profiles", "CASCADE"),
    )
    _ix("drops", "seller_id")
    _ix("drops", "starts_at")

    op.create_table(
        "drop_products",
        sa.Column("drop_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("drop_id", "product_id", name="pk_drop_products"),
        _fk("drop_products", "drop_id", "drops", "CASCADE"),
        _fk("drop_products", "product_id", "products", "CASCADE"),
    )

    op.create_table(
        "drop_subscriptions",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("drop_id", sa.Uuid(), nullable=False),
        sa.Column("notified_at", TS),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_drop_subscriptions"),
        sa.UniqueConstraint("user_id", "drop_id", name="uq_drop_subscriptions_user_drop"),
        _fk("drop_subscriptions", "user_id", "users", "CASCADE"),
        _fk("drop_subscriptions", "drop_id", "drops", "CASCADE"),
    )
    _ix("drop_subscriptions", "user_id")
    _ix("drop_subscriptions", "drop_id")

    op.create_table(
        "wishlist_items",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("board_id", sa.Uuid()),
        sa.Column("saved_price_qc", sa.Integer()),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_wishlist_items"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_wishlist_items_user_product"),
        _fk("wishlist_items", "user_id", "users", "CASCADE"),
        _fk("wishlist_items", "product_id", "products", "CASCADE"),
    )
    for col in ("user_id", "product_id", "board_id"):
        _ix("wishlist_items", col)

    op.create_table(
        "cart_items",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("variant_id", sa.Uuid(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("saved_for_later", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_cart_items"),
        sa.UniqueConstraint("user_id", "variant_id", name="uq_cart_items_user_variant"),
        sa.CheckConstraint("qty BETWEEN 1 AND 10", name="ck_cart_items_qty_range"),
        _fk("cart_items", "user_id", "users", "CASCADE"),
        _fk("cart_items", "variant_id", "variants", "CASCADE"),
    )
    _ix("cart_items", "user_id")
    _ix("cart_items", "variant_id")


def downgrade() -> None:
    for table in (
        "cart_items",
        "wishlist_items",
        "drop_subscriptions",
        "drop_products",
        "drops",
        "collections",
        "follows",
        "reviews",
        "variants",
        "product_images",
    ):
        op.drop_table(table)
    op.execute("DROP INDEX IF EXISTS ix_products_search_trgm")
    for table in ("products", "brands", "subcategories", "categories", "seller_profiles"):
        op.drop_table(table)
