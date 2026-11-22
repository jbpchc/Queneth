"""Seller Studio products: wizard drafts with autosave, publish, archive,
duplicate, and inventory. Every function is scoped to the seller's own boutique."""

import re
import secrets
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Permission, assert_can
from app.core.security import utcnow
from app.core.text import slugify
from app.models.catalog import (
    Brand,
    Category,
    Drop,
    Product,
    ProductImage,
    Subcategory,
    Variant,
    drop_products,
)
from app.models.commerce import OrderItem, OrderStatus, SubOrder
from app.models.user import User
from app.schemas.catalog import ImageOut
from app.schemas.catalog_attributes import ATTRIBUTE_MODELS, VARIANT_AXES, validate_attributes
from app.schemas.studio import (
    CategoryOption,
    InventoryRow,
    InventoryUpdate,
    ProductBasics,
    ProductPatch,
    StudioMeta,
    StudioProduct,
    StudioProductRow,
    StudioVariant,
)
from app.services.boutique_service import own_boutique
from app.services.catalog_index import refresh_denormalized
from app.services.catalog_service import CatalogService
from app.services.media_service import MediaService

MIN_DESCRIPTION = 40
NOT_SOLD = (OrderStatus.CANCELLED.value, OrderStatus.REFUNDED.value)


# ─── Lookups ───────────────────────────────────────────────────────────────


async def meta(session: AsyncSession, user: User) -> StudioMeta:
    assert_can(user, Permission.PRODUCT_CREATE)
    cats = (await session.scalars(select(Category).order_by(Category.sort_order))).all()
    subs = (await session.scalars(select(Subcategory).order_by(Subcategory.sort_order))).all()
    brands = (await session.scalars(select(Brand.name).order_by(Brand.name))).all()
    return StudioMeta(
        categories=[
            CategoryOption(
                slug=c.slug,
                name=c.name,
                subcategories=[
                    {"slug": s.slug, "name": s.name} for s in subs if s.category_id == c.id
                ],
                variant_axes=VARIANT_AXES.get(c.slug, []),
                attribute_schema=c.attribute_schema or {},
            )
            for c in cats
        ],
        brands=list(brands),
    )


async def _owned(session: AsyncSession, user: User, product_id: uuid.UUID) -> Product:
    seller_id = own_boutique(user)
    p = await session.get(Product, product_id)
    if p is None or p.seller_id != seller_id or p.deleted_at is not None:
        raise NotFound("We couldn't find that product.", code="product_not_found")
    return p


async def _variants(session: AsyncSession, product_id: uuid.UUID) -> list[Variant]:
    return list(
        (
            await session.scalars(
                select(Variant).where(Variant.product_id == product_id).order_by(Variant.position)
            )
        ).all()
    )


async def _sold(session: AsyncSession, variant_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not variant_ids:
        return {}
    rows = await session.execute(
        select(OrderItem.variant_id, func.sum(OrderItem.qty))
        .join(SubOrder, SubOrder.id == OrderItem.sub_order_id)
        .where(OrderItem.variant_id.in_(variant_ids), SubOrder.status.notin_(NOT_SOLD))
        .group_by(OrderItem.variant_id)
    )
    return {vid: int(n or 0) for vid, n in rows.all()}


async def _brand(session: AsyncSession, name: str) -> Brand:
    """Existing brand (case-insensitive) or a new fictional one."""
    found = await session.scalar(select(Brand).where(func.lower(Brand.name) == name.lower()))
    if found:
        return found
    base, slug, n = slugify(name) or "brand", slugify(name) or "brand", 2
    while await session.scalar(select(Brand.id).where(Brand.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    brand = Brand(name=name, slug=slug)
    session.add(brand)
    await session.flush()
    return brand


async def _taxonomy(
    session: AsyncSession, category_slug: str, sub_slug: str
) -> tuple[Category, Subcategory]:
    cat = await session.scalar(select(Category).where(Category.slug == category_slug))
    if cat is None:
        raise ValidationFailed("Choose a category.", code="invalid_category")
    sub = await session.scalar(
        select(Subcategory).where(Subcategory.slug == sub_slug, Subcategory.category_id == cat.id)
    )
    if sub is None:
        raise ValidationFailed(f"Choose a {cat.name.lower()} type.", code="invalid_subcategory")
    return cat, sub


async def _unique_slug(session: AsyncSession, text: str, exclude: uuid.UUID | None = None) -> str:
    base = slugify(text)[:150] or "piece"
    slug, n = base, 2
    while True:
        stmt = select(Product.id).where(Product.slug == slug)
        if exclude:
            stmt = stmt.where(Product.id != exclude)
        if await session.scalar(stmt) is None:
            return slug
        slug, n = f"{base}-{n}", n + 1


async def _new_sku(session: AsyncSession, brand: str) -> str:
    letters = "".join(w[0] for w in re.findall(r"[A-Za-z]+", brand))[:2].upper() or "QN"
    while True:
        sku = f"QN-{letters}-{secrets.token_hex(3).upper()}"
        if await session.scalar(select(Variant.id).where(Variant.sku == sku)) is None:
            return sku


# ─── Readiness ─────────────────────────────────────────────────────────────


def attribute_problem(category_slug: str, attrs: dict[str, Any]) -> str | None:
    try:
        validate_attributes(category_slug, attrs)
    except ValidationError as exc:
        err = exc.errors()[0]
        field = ".".join(str(x) for x in err.get("loc", ()) if not isinstance(x, int))
        msg = str(err.get("msg", "")).removeprefix("Value error, ")
        label = field.replace("_", " ") if field else "details"
        return f"Category details: {label} — {msg}"
    return None


def missing(p: Product, variants: list[Variant]) -> list[str]:
    """What still blocks publishing (UX: Zeigarnik — the wizard shows this list)."""
    out: list[str] = []
    if len((p.description or "").strip()) < MIN_DESCRIPTION:
        out.append(f"Write a description (at least {MIN_DESCRIPTION} characters)")
    if not p.images:
        out.append("Add at least one photo")
    if not variants:
        out.append("Add at least one variant with a price")
    if (problem := attribute_problem(p.category.slug, p.attributes or {})) is not None:
        out.append(problem)
    return out


# ─── Output ────────────────────────────────────────────────────────────────


async def to_out(
    session: AsyncSession, settings: Settings, p: Product, variants: list[Variant] | None = None
) -> StudioProduct:
    catalog = CatalogService(session, settings)
    variants = variants if variants is not None else await _variants(session, p.id)
    sold = await _sold(session, [v.id for v in variants])
    drop = await session.scalar(
        select(Drop.title)
        .join(drop_products, drop_products.c.drop_id == Drop.id)
        .where(drop_products.c.product_id == p.id, Drop.starts_at > utcnow())
    )
    return StudioProduct(
        id=p.id,
        slug=p.slug,
        title=p.title,
        brand=p.brand.name,
        category=p.category.slug,
        subcategory=p.subcategory.slug,
        condition=p.condition,
        description=p.description or "",
        authenticity_note=p.authenticity_note,
        tags=list(p.tags or []),
        attributes=dict(p.attributes or {}),
        status=p.status,  # type: ignore[arg-type]
        published_at=p.published_at,
        scheduled_drop=drop,
        images=[
            ImageOut(url=catalog.abs_url(i.url) or "", alt=i.alt, color=i.color) for i in p.images
        ],
        variants=[
            StudioVariant(
                id=v.id,
                sku=v.sku,
                options=v.options,
                price_qc=v.price_qc,
                compare_at_qc=v.compare_at_qc,
                stock=v.stock,
                low_stock_threshold=v.low_stock_threshold,
                sold=sold.get(v.id, 0),
            )
            for v in variants
        ],
        variant_axes=VARIANT_AXES.get(p.category.slug, []),
        missing=missing(p, variants),
        updated_at=p.updated_at,
    )


async def rows(
    session: AsyncSession, settings: Settings, user: User, *, status: str | None, q: str | None
) -> tuple[list[StudioProductRow], dict[str, int]]:
    seller_id = own_boutique(user)
    catalog = CatalogService(session, settings)
    base = select(Product).where(Product.seller_id == seller_id, Product.deleted_at.is_(None))
    counts = dict(
        (
            await session.execute(
                select(Product.status, func.count())
                .where(Product.seller_id == seller_id, Product.deleted_at.is_(None))
                .group_by(Product.status)
            )
        ).all()
    )
    if status:
        base = base.where(Product.status == status)
    if q and q.strip():
        base = base.where(func.lower(Product.title).contains(q.strip().lower()))
    products = list((await session.scalars(base.order_by(Product.updated_at.desc()))).all())
    ids = [p.id for p in products]
    variant_rows = (
        (await session.execute(select(Variant).where(Variant.product_id.in_(ids)))).scalars().all()
        if ids
        else []
    )
    by_product: dict[uuid.UUID, list[Variant]] = {}
    for v in variant_rows:
        by_product.setdefault(v.product_id, []).append(v)
    sold = await _sold(session, [v.id for v in variant_rows])
    out = [
        StudioProductRow(
            id=p.id,
            slug=p.slug,
            title=p.title,
            category=p.category.slug,
            status=p.status,  # type: ignore[arg-type]
            image=catalog.abs_url(p.images[0].url) if p.images else None,
            min_price_qc=p.min_price_qc,
            total_stock=p.total_stock,
            variant_count=len(by_product.get(p.id, [])),
            low_stock=any(v.stock <= v.low_stock_threshold for v in by_product.get(p.id, [])),
            view_count=p.view_count,
            wishlist_count=p.wishlist_count,
            sold=sum(sold.get(v.id, 0) for v in by_product.get(p.id, [])),
            updated_at=p.updated_at,
        )
        for p in products
    ]
    return out, {str(k): int(v) for k, v in counts.items()}


# ─── Create, autosave, publish ─────────────────────────────────────────────


async def create(session: AsyncSession, user: User, body: ProductBasics) -> Product:
    """Step 1 (Basics) creates the draft; later steps autosave onto it."""
    assert_can(user, Permission.PRODUCT_CREATE)
    seller_id = own_boutique(user)
    cat, sub = await _taxonomy(session, body.category, body.subcategory)
    brand = await _brand(session, body.brand)
    p = Product(
        seller_id=seller_id,
        brand_id=brand.id,
        category_id=cat.id,
        subcategory_id=sub.id,
        title=body.title,
        slug=await _unique_slug(session, f"{brand.name} {body.title}"),
        description="",
        condition=body.condition,
        attributes={},
        tags=[],
        status="draft",
    )
    p.brand, p.category, p.subcategory = brand, cat, sub
    p.images = []
    session.add(p)
    await session.flush()
    refresh_denormalized(p, [])
    await session.commit()
    await session.refresh(p)
    return p


def _clean_attributes(category_slug: str, attrs: dict[str, Any]) -> dict[str, Any]:
    """Drafts keep partial details, but only fields the category knows."""
    allowed = set(ATTRIBUTE_MODELS[category_slug].model_fields)
    return {k: v for k, v in attrs.items() if k in allowed and v not in (None, "", [])}


async def _set_images(
    session: AsyncSession, settings: Settings, user: User, p: Product, images: list
) -> None:  # type: ignore[type-arg]
    media = MediaService(session, settings)
    current = {i.url: i for i in p.images}
    new: list[ProductImage] = []
    for pos, img in enumerate(images):
        if img.asset_id:
            asset = await media.get_ready_asset(user, img.asset_id, "product")
            url = media.to_out(asset).url or ""
        else:
            url = next(
                (u for u in current if img.url and (img.url == u or img.url.endswith(u))), None
            )
            if url is None:
                raise ValidationFailed("Upload photos before adding them.", code="invalid_image")
        new.append(ProductImage(url=url, alt=img.alt.strip(), position=pos, color=img.color))
    # UX: drag-to-reorder — the order sent is the gallery order; the first is the cover.
    p.images = new


async def _set_variants(
    session: AsyncSession, p: Product, axes: list[str], payload: list
) -> list[Variant]:  # type: ignore[type-arg]
    existing = {v.id: v for v in await _variants(session, p.id)}
    seen_combos: set[tuple[tuple[str, str], ...]] = set()
    keep: list[Variant] = []
    for pos, item in enumerate(payload):
        unknown = set(item.options) - set(axes)
        if unknown:
            raise ValidationFailed(
                f"{p.category.name} variants use {', '.join(axes)} "
                f"(not {', '.join(sorted(unknown))}).",
                code="invalid_variant_option",
            )
        combo = tuple(sorted(item.options.items()))
        if combo in seen_combos:
            raise ValidationFailed("Two variants have the same options.", code="duplicate_variant")
        seen_combos.add(combo)
        if item.id is not None:
            v = existing.get(item.id)
            if v is None:
                raise NotFound("That variant isn't part of this product.", code="variant_not_found")
        else:
            v = Variant(product_id=p.id, sku=await _new_sku(session, p.brand.name))
            session.add(v)
        v.options = dict(item.options)
        v.price_qc = item.price_qc
        v.compare_at_qc = item.compare_at_qc
        v.stock = item.stock
        v.low_stock_threshold = item.low_stock_threshold
        v.position = pos
        keep.append(v)
    removed = [v for vid, v in existing.items() if vid not in {k.id for k in keep}]
    if removed:
        ordered = set(
            (
                await session.scalars(
                    select(OrderItem.variant_id).where(
                        OrderItem.variant_id.in_([v.id for v in removed])
                    )
                )
            ).all()
        )
        if ordered:
            raise Conflict(
                "A variant that was already ordered can't be deleted. Set its stock to 0 instead.",
                code="variant_has_orders",
            )
        for v in removed:
            await session.delete(v)
    await session.flush()
    return keep


async def patch(
    session: AsyncSession, settings: Settings, user: User, product_id: uuid.UUID, body: ProductPatch
) -> Product:
    """Autosave any wizard step. Published products must stay complete."""
    assert_can(user, Permission.PRODUCT_UPDATE)
    p = await _owned(session, user, product_id)
    data = body.model_dump(exclude_unset=True)

    if "title" in data or "brand" in data:
        if body.brand:
            brand = await _brand(session, body.brand)
            p.brand_id, p.brand = brand.id, brand
        if body.title:
            p.title = body.title
        if p.status == "draft":  # live URLs never change under shoppers
            p.slug = await _unique_slug(session, f"{p.brand.name} {p.title}", p.id)
    if "category" in data or "subcategory" in data:
        cat, sub = await _taxonomy(
            session, body.category or p.category.slug, body.subcategory or p.subcategory.slug
        )
        if cat.id != p.category_id and p.status != "draft":
            raise Conflict(
                "A published piece can't change category. Duplicate it instead.",
                code="category_locked",
            )
        if cat.id != p.category_id:
            p.attributes = {}
        p.category_id, p.category = cat.id, cat
        p.subcategory_id, p.subcategory = sub.id, sub
    for field in ("condition", "authenticity_note", "tags"):
        if field in data:
            setattr(p, field, data[field])
    if "description" in data:
        p.description = (body.description or "").strip()
    if body.attributes is not None:
        p.attributes = _clean_attributes(p.category.slug, body.attributes)
    if body.images is not None:
        await _set_images(session, settings, user, p, body.images)
    variants = (
        await _set_variants(session, p, VARIANT_AXES.get(p.category.slug, []), body.variants)
        if body.variants is not None
        else await _variants(session, p.id)
    )

    if p.status == "active":
        problems = missing(p, variants)
        if problems:
            raise ValidationFailed(
                "A published piece must stay complete: " + "; ".join(problems) + ".",
                code="incomplete_product",
                details={"missing": problems},
            )
        p.attributes = validate_attributes(p.category.slug, p.attributes or {})
    refresh_denormalized(p, variants)
    p.updated_at = utcnow()
    await session.commit()
    await session.refresh(p)
    return p


async def publish(session: AsyncSession, user: User, product_id: uuid.UUID) -> Product:
    assert_can(user, Permission.PRODUCT_UPDATE)
    p = await _owned(session, user, product_id)
    if p.status == "removed":
        raise Conflict(
            "This piece was taken down by moderation. Contact the Queneth team to appeal.",
            code="product_removed",
        )
    variants = await _variants(session, p.id)
    problems = missing(p, variants)
    if problems:
        raise ValidationFailed(
            "Almost there: " + "; ".join(problems) + ".",
            code="incomplete_product",
            details={"missing": problems},
        )
    p.attributes = validate_attributes(p.category.slug, p.attributes or {})
    p.status = "active"
    # A product in a scheduled drop already carries the drop's start time.
    if p.published_at is None:
        p.published_at = utcnow()
    refresh_denormalized(p, variants)
    await session.commit()
    await session.refresh(p)
    return p


async def set_archived(
    session: AsyncSession, user: User, ids: list[uuid.UUID], archived: bool
) -> int:
    """Bulk archive / restore. Restored pieces go live again only if complete."""
    assert_can(user, Permission.PRODUCT_ARCHIVE)
    seller_id = own_boutique(user)
    products = list(
        (
            await session.scalars(
                select(Product).where(
                    Product.id.in_(ids),
                    Product.seller_id == seller_id,
                    Product.deleted_at.is_(None),
                )
            )
        ).all()
    )
    if len(products) != len(set(ids)):
        raise NotFound("Some of those products aren't yours.", code="product_not_found")
    changed = 0
    for p in products:
        if archived and p.status != "archived":
            p.status, changed = "archived", changed + 1
        elif not archived and p.status == "archived":
            complete = not missing(p, await _variants(session, p.id))
            p.status = "active" if complete and p.published_at else "draft"
            changed += 1
    await session.commit()
    return changed


async def duplicate(session: AsyncSession, user: User, product_id: uuid.UUID) -> Product:
    """Copy as a new draft (stock starts at 0 so no phantom inventory)."""
    assert_can(user, Permission.PRODUCT_CREATE)
    src = await _owned(session, user, product_id)
    title = f"{src.title} (copy)"[:120]
    copy = Product(
        seller_id=src.seller_id,
        brand_id=src.brand_id,
        category_id=src.category_id,
        subcategory_id=src.subcategory_id,
        title=title,
        slug=await _unique_slug(session, f"{src.brand.name} {title}"),
        description=src.description,
        condition=src.condition,
        authenticity_note=src.authenticity_note,
        attributes=dict(src.attributes or {}),
        tags=list(src.tags or []),
        status="draft",
    )
    copy.brand, copy.category, copy.subcategory = src.brand, src.category, src.subcategory
    copy.images = [
        ProductImage(url=i.url, alt=i.alt, position=i.position, color=i.color) for i in src.images
    ]
    session.add(copy)
    await session.flush()
    variants = []
    for v in await _variants(session, src.id):
        nv = Variant(
            product_id=copy.id,
            sku=await _new_sku(session, src.brand.name),
            options=dict(v.options),
            price_qc=v.price_qc,
            compare_at_qc=v.compare_at_qc,
            stock=0,
            low_stock_threshold=v.low_stock_threshold,
            position=v.position,
        )
        session.add(nv)
        variants.append(nv)
    await session.flush()
    refresh_denormalized(copy, variants)
    await session.commit()
    await session.refresh(copy)
    return copy


async def delete_draft(session: AsyncSession, user: User, product_id: uuid.UUID) -> None:
    assert_can(user, Permission.PRODUCT_ARCHIVE)
    p = await _owned(session, user, product_id)
    if p.status != "draft":
        raise Conflict("Only drafts can be deleted. Archive published pieces.", code="not_draft")
    p.deleted_at = utcnow()
    await session.commit()


async def get(session: AsyncSession, user: User, product_id: uuid.UUID) -> Product:
    return await _owned(session, user, product_id)


# ─── Inventory ─────────────────────────────────────────────────────────────


async def inventory(
    session: AsyncSession, settings: Settings, user: User, *, low_only: bool
) -> list[InventoryRow]:
    assert_can(user, Permission.INVENTORY_MANAGE)
    seller_id = own_boutique(user)
    catalog = CatalogService(session, settings)
    stmt = (
        select(Variant, Product)
        .join(Product, Product.id == Variant.product_id)
        .where(Product.seller_id == seller_id, Product.deleted_at.is_(None))
        .order_by(Product.title, Variant.position)
    )
    if low_only:
        stmt = stmt.where(Variant.stock <= Variant.low_stock_threshold, Product.status == "active")
    return [
        InventoryRow(
            variant_id=v.id,
            product_id=p.id,
            product_title=p.title,
            product_status=p.status,  # type: ignore[arg-type]
            image=catalog.abs_url(p.images[0].url) if p.images else None,
            sku=v.sku,
            options=v.options,
            price_qc=v.price_qc,
            stock=v.stock,
            low_stock_threshold=v.low_stock_threshold,
            low_stock=v.stock <= v.low_stock_threshold,
        )
        for v, p in (await session.execute(stmt)).all()
    ]


async def update_inventory(
    session: AsyncSession, user: User, updates: list[InventoryUpdate]
) -> int:
    assert_can(user, Permission.INVENTORY_MANAGE)
    seller_id = own_boutique(user)
    ids = [u.variant_id for u in updates]
    found = {
        v.id: (v, p)
        for v, p in (
            await session.execute(
                select(Variant, Product)
                .join(Product, Product.id == Variant.product_id)
                .where(Variant.id.in_(ids), Product.seller_id == seller_id)
                .with_for_update(of=Variant)
            )
        ).all()
    }
    if len(found) != len(set(ids)):
        raise NotFound("Some of those variants aren't yours.", code="variant_not_found")
    touched: dict[uuid.UUID, Product] = {}
    for u in updates:
        v, p = found[u.variant_id]
        if u.stock is not None:
            v.stock = u.stock
        if u.low_stock_threshold is not None:
            v.low_stock_threshold = u.low_stock_threshold
        touched[p.id] = p
    await session.flush()
    for p in touched.values():
        refresh_denormalized(p, await _variants(session, p.id))
    await session.commit()
    return len(updates)
