"""Catalog reads: listings with facets, typo-tolerant search, product detail,
home rails, boutiques, collections, drops.

Approach: SQL selects the *visible* catalog (active, published, approved
boutique, not deleted; on Postgres the search query is pre-filtered with the
pg_trgm index), then filtering on array-valued attributes (sizes, colors,
notes…), disjunctive facet counting, relevance scoring and keyset pagination
run in Python over that set. That keeps one code path for Postgres and the
SQLite test database and is comfortably fast for a boutique-scale catalog
(hundreds to a few thousand products). See docs/ASSUMPTIONS.md (#57).
"""

import bisect
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.errors import NotFound, ValidationFailed
from app.core.pagination import clamp_limit, decode_cursor, encode_cursor
from app.core.palette import color_hex
from app.core.security import utcnow
from app.models.catalog import (
    Category,
    Collection,
    Drop,
    DropSubscription,
    Follow,
    Product,
    Review,
    SellerProfile,
    drop_products,
)
from app.models.user import User
from app.schemas.catalog import (
    Badge,
    BoutiqueCard,
    BoutiqueDetail,
    CategoryOut,
    CollectionOut,
    DropOut,
    DropRef,
    Facets,
    FacetValue,
    HomeOut,
    ImageOut,
    PriceRange,
    ProductCard,
    ProductDetail,
    ProductListing,
    Ref,
    ReviewOut,
    ReviewSummary,
    SortKey,
    SubcategoryOut,
    Suggestion,
    Swatch,
    VariantOut,
)
from app.schemas.catalog_attributes import VARIANT_AXES
from app.services.catalog_index import size_sort_key

CONDITION_LABELS = {
    "new": "New",
    "preloved_excellent": "Pre-loved · Excellent",
    "preloved_good": "Pre-loved · Good",
}
EXTRA_LABELS = {
    "notes": "Notes",
    "concentration": "Concentration",
    "family": "Olfactory family",
    "material": "Material",
    "closure": "Closure",
    "fit": "Fit",
    "fabric": "Fabric",
    "heel": "Heel height",
    "upper": "Upper",
}
NEW_DROP_WINDOW = timedelta(days=14)


def fold(text: str) -> str:
    """Lowercase and strip accents: "Néroli" matches "neroli"."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9&']+", fold(text)) if len(t) >= 2]


@dataclass
class ListingParams:
    q: str | None = None
    category: str | None = None
    subcategory: str | None = None
    brands: list[str] = field(default_factory=list)
    boutiques: list[str] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    price_min: int | None = None
    price_max: int | None = None
    #: Category facets as {"notes": ["bergamot"], "family": ["Woody"]}
    facets: dict[str, list[str]] = field(default_factory=dict)
    tag: str | None = None
    in_stock: bool = False
    sort: SortKey = "curated"
    cursor: str | None = None
    limit: int | None = None


class Matcher:
    """Typo-tolerant token matching: substring first, then fuzzy (ratio ≥ 0.78)."""

    def __init__(self, query: str):
        self.tokens = tokenize(query)
        self.corrections: dict[str, str] = {}

    def score(self, product: Product) -> float | None:
        words = set(tokenize(product.search_text))
        title = fold(product.title)
        total = 0.0
        for tok in self.tokens:
            if any(tok in w for w in words):
                best = 1.0
            else:
                best, word = 0.0, ""
                for w in words:
                    if abs(len(w) - len(tok)) <= 3:
                        r = SequenceMatcher(None, tok, w).ratio()
                        if r > best:
                            best, word = r, w
                if best < 0.78:
                    return None
                self.corrections.setdefault(tok, word)
            total += best + (0.6 if tok in title else 0)
        return total

    def corrected(self) -> str | None:
        if not self.corrections:
            return None
        return " ".join(self.corrections.get(t, t) for t in self.tokens)


class CatalogService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.now = utcnow()

    # ─── helpers ─────────────────────────────────────────────────────────

    def abs_url(self, url: str | None) -> str | None:
        if url and url.startswith("/"):
            return f"{self.settings.api_public_url}{url}"
        return url

    async def visible_products(self, q: str | None = None) -> list[Product]:
        stmt = (
            select(Product)
            .join(SellerProfile, Product.seller_id == SellerProfile.id)
            .where(
                Product.status == "active",
                Product.deleted_at.is_(None),
                Product.published_at.is_not(None),
                Product.published_at <= self.now,
                SellerProfile.status == "approved",
            )
        )
        if q and self.session.bind.dialect.name == "postgresql":
            # Uses ix_products_search_trgm; Python re-scores the shortlist.
            toks = tokenize(q)
            if toks:
                stmt = stmt.where(
                    or_(
                        *[Product.search_text.ilike(f"%{t}%") for t in toks],
                        *[func.word_similarity(t, Product.search_text) > 0.3 for t in toks],
                    )
                )
        return list((await self.session.scalars(stmt)).unique().all())

    async def live_drop_product_ids(self) -> set[uuid.UUID]:
        rows = await self.session.execute(
            select(drop_products.c.product_id)
            .join(Drop, Drop.id == drop_products.c.drop_id)
            .where(Drop.starts_at <= self.now, or_(Drop.ends_at.is_(None), Drop.ends_at > self.now))
        )
        return {r[0] for r in rows}

    def badges(self, p: Product, live_drop_ids: set[uuid.UUID]) -> list[Badge]:
        out: list[Badge] = []
        published = p.published_at
        if p.id in live_drop_ids or (
            "new-drop" in (p.tags or []) and published and self.now - published < NEW_DROP_WINDOW
        ):
            out.append("new_drop")
        if p.total_stock == 0:
            out.append("sold_out")
        elif p.total_stock <= 3:
            out.append("low_stock")  # the real count, never invented
        if p.compare_at_qc:
            out.append("sale")
        if p.condition != "new":
            out.append("preloved")
        if p.is_connoisseur_pick:
            out.append("connoisseur_pick")
        return out

    def card(
        self, p: Product, live_drop_ids: set[uuid.UUID], color: str | None = None
    ) -> ProductCard:
        """`color` (a bag or order line's variant color) puts that color's photos first."""
        images = list(p.images or [])
        if color and any(i.color == color for i in images):
            images.sort(key=lambda i: i.color != color)  # stable: keeps photo order
        first = images[0] if images else None
        # Hover shows another angle (the close-up), cross-faded in by the UI.
        hover = images[1] if len(images) > 1 else None
        return ProductCard(
            id=p.id,
            slug=p.slug,
            title=p.title,
            brand=Ref(name=p.brand.name, slug=p.brand.slug),
            boutique=Ref(name=p.seller.boutique_name, slug=p.seller.slug),
            category=p.category.slug,
            subcategory=p.subcategory.slug,
            price_qc=p.min_price_qc,
            max_price_qc=p.max_price_qc,
            compare_at_qc=p.compare_at_qc,
            image=ImageOut(url=self.abs_url(first.url) or "", alt=first.alt, color=first.color)
            if first
            else None,
            hover_image=ImageOut(
                url=self.abs_url(hover.url) or "", alt=hover.alt, color=hover.color
            )
            if hover
            else None,
            colors=[Swatch(name=c, hex=color_hex(c)) for c in p.colors or []],
            sizes=p.sizes or [],
            rating_avg=round(p.rating_avg, 1),
            rating_count=p.rating_count,
            condition=p.condition,
            total_stock=p.total_stock,
            badges=self.badges(p, live_drop_ids),
        )

    async def cards(self, products: Iterable[Product]) -> list[ProductCard]:
        live = await self.live_drop_product_ids()
        return [self.card(p, live) for p in products]

    # ─── listings & search ───────────────────────────────────────────────

    async def listing(self, params: ListingParams) -> tuple[ProductListing, str | None]:
        products = await self.visible_products(params.q)
        matcher = Matcher(params.q) if params.q and tokenize(params.q) else None
        relevance: dict[uuid.UUID, float] = {}
        if matcher:
            for p in products:
                s = matcher.score(p)
                if s is not None:
                    relevance[p.id] = s
            products = [p for p in products if p.id in relevance]
        if params.category:
            products = [p for p in products if p.category.slug == params.category]
        if params.tag:
            products = [p for p in products if params.tag in (p.tags or [])]

        checks = self._dimension_checks(params)
        filtered = [p for p in products if all(check(p) for check in checks.values())]
        facets = self._facets(products, checks, params)

        sort_key = self._sort_key(params.sort, relevance)
        ordered = sorted(filtered, key=sort_key)
        keys = [sort_key(p) for p in ordered]
        start = 0
        if pos := decode_cursor(params.cursor):
            try:
                marker = (*pos["k"], pos["id"])
                start = bisect.bisect_right([(*k[:-1], k[-1]) for k in keys], tuple(marker))
            except (KeyError, TypeError) as exc:
                raise ValidationFailed(
                    "That page link is no longer valid.", code="invalid_cursor"
                ) from exc
        size = clamp_limit(params.limit)
        page = ordered[start : start + size]
        next_cursor = None
        if start + size < len(ordered):
            last = keys[start + size - 1]
            next_cursor = encode_cursor({"k": list(last[:-1]), "id": last[-1]})
        pick = next((p.id for p in ordered if p.is_connoisseur_pick and p.total_stock), None)
        listing = ProductListing(
            items=await self.cards(page),
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
            total=len(ordered),
            facets=facets,
            connoisseur_pick_id=pick,
        )
        return listing, (matcher.corrected() if matcher else None)

    def _dimension_checks(self, p: ListingParams) -> dict[str, Callable[[Product], bool]]:
        checks: dict[str, Callable[[Product], bool]] = {}
        if p.subcategory:
            checks["subcategory"] = lambda x: x.subcategory.slug == p.subcategory
        if p.brands:
            checks["brand"] = lambda x: x.brand.slug in p.brands
        if p.boutiques:
            checks["boutique"] = lambda x: x.seller.slug in p.boutiques
        if p.sizes:
            checks["size"] = lambda x: bool(set(x.sizes or []) & set(p.sizes))
        if p.colors:
            checks["color"] = lambda x: bool(set(x.colors or []) & set(p.colors))
        if p.conditions:
            checks["condition"] = lambda x: x.condition in p.conditions
        if p.price_min is not None or p.price_max is not None:
            lo, hi = p.price_min or 0, p.price_max or 10**12
            checks["price"] = lambda x: lo <= x.min_price_qc <= hi
        if p.in_stock:
            checks["stock"] = lambda x: x.total_stock > 0
        for key, values in p.facets.items():
            if values:
                wanted = {fold(v) for v in values}
                checks[f"x:{key}"] = lambda x, k=key, w=wanted: bool(
                    {fold(v) for v in (x.facet_values or {}).get(k, [])} & w
                )
        return checks

    def _facets(
        self,
        products: list[Product],
        checks: dict[str, Callable[[Product], bool]],
        params: ListingParams,
    ) -> Facets:
        def excluding(dim: str) -> list[Product]:
            return [p for p in products if all(c(p) for d, c in checks.items() if d != dim)]

        def counted(
            rows: list[Product], getter: Callable[[Product], Iterable[tuple[str, str]]]
        ) -> list[FacetValue]:
            counts: Counter[tuple[str, str]] = Counter()
            for row in rows:
                counts.update(set(getter(row)))
            return [FacetValue(value=v, label=lbl, count=n) for (v, lbl), n in counts.items()]

        subs = sorted(
            counted(excluding("subcategory"), lambda x: [(x.subcategory.slug, x.subcategory.name)]),
            key=lambda f: -f.count,
        )
        brands = sorted(
            counted(excluding("brand"), lambda x: [(x.brand.slug, x.brand.name)]),
            key=lambda f: f.label,
        )
        boutiques = sorted(
            counted(excluding("boutique"), lambda x: [(x.seller.slug, x.seller.boutique_name)]),
            key=lambda f: f.label,
        )
        sizes = sorted(
            counted(excluding("size"), lambda x: [(s, s) for s in x.sizes or []]),
            key=lambda f: size_sort_key(f.value),
        )
        colors = sorted(
            counted(excluding("color"), lambda x: [(c, c) for c in x.colors or []]),
            key=lambda f: -f.count,
        )
        for c in colors:
            c.hex = color_hex(c.value)
        conditions = counted(
            excluding("condition"),
            lambda x: [(x.condition, CONDITION_LABELS.get(x.condition, x.condition))],
        )
        priced = excluding("price")
        price = PriceRange(
            min=min((p.min_price_qc for p in priced), default=0),
            max=max((p.min_price_qc for p in priced), default=0),
        )
        extra: dict[str, list[FacetValue]] = {}
        if params.category:
            keys = sorted({k for p in products for k in (p.facet_values or {})})
            for key in keys:
                values = counted(
                    excluding(f"x:{key}"),
                    lambda x, k=key: [
                        (v, v.title() if k == "notes" else v)
                        for v in (x.facet_values or {}).get(k, [])
                    ],
                )
                values.sort(key=lambda f: (-f.count, f.label))
                extra[key] = values[:24]
        return Facets(
            subcategories=subs,
            brands=brands,
            boutiques=boutiques,
            sizes=sizes,
            colors=colors,
            conditions=conditions,
            price=price,
            extra=extra,
        )

    def _sort_key(
        self, sort: SortKey, relevance: dict[uuid.UUID, float]
    ) -> Callable[[Product], tuple[Any, ...]]:
        def ts(p: Product) -> float:
            return p.published_at.timestamp() if p.published_at else 0.0

        def key(p: Product) -> tuple[Any, ...]:
            sold_out = 0 if p.total_stock > 0 else 1  # available pieces first, always
            base: tuple[Any, ...]
            if sort == "newest":
                base = (-ts(p),)
            elif sort == "price_asc":
                base = (p.min_price_qc,)
            elif sort == "price_desc":
                base = (-p.min_price_qc,)
            elif sort == "most_wished":
                base = (-p.wishlist_count,)
            elif sort == "top_rated":
                base = (-round(p.rating_avg, 2), -p.rating_count)
            else:  # curated (with search relevance first when there's a query)
                base = (-round(relevance.get(p.id, 0), 3), -p.curated_score, -ts(p))
            return (sold_out, *base, str(p.id))

        return key

    async def suggest(self, q: str) -> Suggestion:
        listing, corrected = await self.listing(ListingParams(q=q, limit=6))
        folded = fold(q)
        products = await self.visible_products()
        brands = {(p.brand.name, p.brand.slug) for p in products if folded in fold(p.brand.name)}
        sellers = {
            p.seller.id: p.seller for p in products if folded in fold(p.seller.boutique_name)
        }
        cats = {
            (p.subcategory.name, f"{p.category.slug}/{p.subcategory.slug}")
            for p in products
            if folded in fold(p.subcategory.name)
        }
        cats |= {
            (p.category.name, p.category.slug) for p in products if folded in fold(p.category.name)
        }
        return Suggestion(
            products=listing.items,
            brands=[Ref(name=n, slug=s) for n, s in sorted(brands)][:4],
            boutiques=[self.boutique_card(s) for s in list(sellers.values())[:3]],
            categories=[Ref(name=n, slug=s) for n, s in sorted(cats)][:4],
            corrected=corrected,
        )

    # ─── product page ────────────────────────────────────────────────────

    async def product_detail(self, slug: str, user: User | None) -> ProductDetail:
        product = await self.session.scalar(
            select(Product).where(Product.slug == slug).options(selectinload(Product.variants))
        )
        visible = (
            product is not None
            and product.status == "active"
            and product.deleted_at is None
            and product.published_at is not None
            and product.published_at <= self.now
            and product.seller.status == "approved"
        )
        if not visible:
            raise NotFound("This piece isn't available.", code="product_not_found")
        assert product is not None
        live = await self.live_drop_product_ids()
        catalog = await self.visible_products()
        reviews = list(
            (
                await self.session.scalars(
                    select(Review)
                    .where(Review.product_id == product.id, Review.status == "published")
                    .order_by(Review.created_at.desc())
                )
            ).all()
        )
        drop = await self.session.scalar(
            select(Drop)
            .join(drop_products, Drop.id == drop_products.c.drop_id)
            .where(drop_products.c.product_id == product.id)
        )
        boutique = await self.boutique_card_with_state(product.seller, user)
        return ProductDetail(
            id=product.id,
            slug=product.slug,
            title=product.title,
            brand=Ref(name=product.brand.name, slug=product.brand.slug),
            category=Ref(name=product.category.name, slug=product.category.slug),
            subcategory=Ref(name=product.subcategory.name, slug=product.subcategory.slug),
            description=product.description,
            condition=product.condition,
            authenticity_note=product.authenticity_note,
            attributes=product.attributes,
            tags=product.tags or [],
            images=[
                ImageOut(url=self.abs_url(i.url) or "", alt=i.alt, color=i.color)
                for i in product.images
            ],
            variants=[
                VariantOut(
                    id=v.id,
                    sku=v.sku,
                    options=v.options,
                    price_qc=v.price_qc,
                    compare_at_qc=v.compare_at_qc,
                    stock=v.stock,
                    low_stock=0 < v.stock <= v.low_stock_threshold,
                )
                for v in product.variants
            ],
            variant_axes=[
                a
                for a in VARIANT_AXES.get(product.category.slug, [])
                if any(a in v.options for v in product.variants)
            ]
            + (["metal"] if any("metal" in v.options for v in product.variants) else []),
            price_qc=product.min_price_qc,
            max_price_qc=product.max_price_qc,
            compare_at_qc=product.compare_at_qc,
            total_stock=product.total_stock,
            colors=[Swatch(name=c, hex=color_hex(c)) for c in product.colors or []],
            sizes=product.sizes or [],
            badges=self.badges(product, live),
            boutique=boutique,
            review_summary=summarize_reviews(reviews),
            reviews=[review_out(r) for r in reviews[:6]],
            drop=DropRef(
                slug=drop.slug, title=drop.title, starts_at=drop.starts_at, ends_at=drop.ends_at
            )
            if drop
            else None,
            published_at=product.published_at,
            you_may_also_love=[self.card(p, live) for p in also_love(product, catalog)],
            complete_the_look=[self.card(p, live) for p in complete_the_look(product, catalog)],
            similar_scents=[self.card(p, live) for p in similar_scents(product, catalog)],
        )

    async def reviews(
        self, slug: str, *, cursor: str | None, limit: int | None, with_photos: bool
    ) -> tuple[list[ReviewOut], str | None]:
        product_id = await self.session.scalar(select(Product.id).where(Product.slug == slug))
        if product_id is None:
            raise NotFound("This piece isn't available.", code="product_not_found")
        size = clamp_limit(limit)
        stmt = (
            select(Review)
            .where(Review.product_id == product_id, Review.status == "published")
            .order_by(Review.created_at.desc(), Review.id.desc())
        )
        if with_photos:
            stmt = (
                stmt.where(func.json_array_length(Review.photos) > 0)
                if self.session.bind.dialect.name == "sqlite"
                else stmt.where(func.jsonb_array_length(Review.photos) > 0)
            )
        if pos := decode_cursor(cursor):
            created, last = datetime.fromisoformat(pos["created_at"]), uuid.UUID(pos["id"])
            stmt = stmt.where(
                (Review.created_at < created)
                | ((Review.created_at == created) & (Review.id < last))
            )
        rows = list((await self.session.scalars(stmt.limit(size + 1))).all())
        nxt = None
        if len(rows) > size:
            rows = rows[:size]
            nxt = encode_cursor(
                {"created_at": rows[-1].created_at.isoformat(), "id": str(rows[-1].id)}
            )
        return [review_out(r) for r in rows], nxt

    # ─── boutiques ───────────────────────────────────────────────────────

    def boutique_card(
        self, s: SellerProfile, product_count: int = 0, following: bool = False
    ) -> BoutiqueCard:
        return BoutiqueCard(
            id=s.id,
            name=s.boutique_name,
            slug=s.slug,
            tagline=s.tagline,
            city=s.city,
            logo_url=self.abs_url(s.logo_url),
            banner_url=self.abs_url(s.banner_url),
            follower_count=s.follower_count,
            product_count=product_count,
            is_following=following,
        )

    async def _following(
        self, user: User | None, seller_ids: Iterable[uuid.UUID]
    ) -> set[uuid.UUID]:
        ids = list(seller_ids)
        if user is None or not ids:
            return set()
        rows = await self.session.scalars(
            select(Follow.seller_id).where(Follow.buyer_id == user.id, Follow.seller_id.in_(ids))
        )
        return set(rows.all())

    async def boutique_card_with_state(self, s: SellerProfile, user: User | None) -> BoutiqueCard:
        count = await self.session.scalar(
            select(func.count())
            .select_from(Product)
            .where(
                Product.seller_id == s.id,
                Product.status == "active",
                Product.deleted_at.is_(None),
                Product.published_at <= self.now,
            )
        )
        return self.boutique_card(s, count or 0, s.id in await self._following(user, [s.id]))

    async def boutiques(self, user: User | None) -> list[BoutiqueCard]:
        sellers = list(
            (
                await self.session.scalars(
                    select(SellerProfile)
                    .where(SellerProfile.status == "approved")
                    .order_by(SellerProfile.boutique_name)
                )
            ).all()
        )
        counts = Counter(p.seller_id for p in await self.visible_products())
        following = await self._following(user, [s.id for s in sellers])
        return [self.boutique_card(s, counts[s.id], s.id in following) for s in sellers]

    async def boutique(self, slug: str, user: User | None) -> BoutiqueDetail:
        s = await self.session.scalar(
            select(SellerProfile).where(
                SellerProfile.slug == slug, SellerProfile.status == "approved"
            )
        )
        if s is None:
            raise NotFound("We couldn't find that boutique.", code="boutique_not_found")
        card = await self.boutique_card_with_state(s, user)
        avg, count = (
            await self.session.execute(
                select(func.coalesce(func.avg(Review.rating), 0), func.count(Review.id))
                .join(Product, Product.id == Review.product_id)
                .where(Product.seller_id == s.id, Review.status == "published")
            )
        ).one()
        pinned = [uuid.UUID(i) for i in (s.featured_product_ids or [])]
        visible = {p.id: p for p in await self.visible_products() if p.id in set(pinned)}
        featured = await self.cards([visible[i] for i in pinned if i in visible])
        return BoutiqueDetail(
            **card.model_dump(),
            bio=s.bio,
            return_policy=s.return_policy,
            rating_avg=round(float(avg), 1),
            rating_count=count,
            since=s.approved_at,
            featured=featured,
            lookbook=[
                ImageOut(
                    url=self.abs_url(x["url"]) or "",
                    alt=x.get("caption") or f"{s.boutique_name} lookbook",
                )
                for x in (s.lookbook or [])
            ],
        )

    # ─── categories, collections, drops, home ────────────────────────────

    def covers(self, products: list[Product], n: int = 4) -> list[str]:
        """Cover photos for a category or subcategory, taken from the sellers'
        own listings: most-wished first, then newest, one per seller first so a
        single boutique doesn't fill the tile."""
        ranked = sorted(
            (p for p in products if p.images and p.total_stock > 0),
            key=lambda p: (
                -p.wishlist_count,
                -(p.published_at.timestamp() if p.published_at else 0),
            ),
        )
        picked: list[str] = []
        sellers: set[uuid.UUID] = set()
        for pass_ in (0, 1):  # first one per seller, then fill up
            for p in ranked:
                if len(picked) >= n:
                    return picked
                if pass_ == 0 and p.seller_id in sellers:
                    continue
                url = self.abs_url(p.images[0].url)
                if url and url not in picked:
                    picked.append(url)
                    sellers.add(p.seller_id)
        return picked

    async def categories(self, products: list[Product] | None = None) -> list[CategoryOut]:
        products = products if products is not None else await self.visible_products()
        cats = list(
            (await self.session.scalars(select(Category).order_by(Category.sort_order))).all()
        )
        by_cat: dict[uuid.UUID, list[Product]] = defaultdict(list)
        by_sub: dict[uuid.UUID, list[Product]] = defaultdict(list)
        for p in products:
            by_cat[p.category_id].append(p)
            by_sub[p.subcategory_id].append(p)
        out = []
        for c in cats:
            covers = self.covers(by_cat[c.id])
            out.append(
                CategoryOut(
                    name=c.name,
                    slug=c.slug,
                    tagline=c.tagline,
                    product_count=len(by_cat[c.id]),
                    cover_url=covers[0] if covers else None,
                    cover_images=covers,
                    subcategories=[
                        SubcategoryOut(
                            name=sc.name,
                            slug=sc.slug,
                            product_count=len(by_sub[sc.id]),
                            cover_url=next(iter(self.covers(by_sub[sc.id], 1)), None),
                        )
                        for sc in c.subcategories
                    ],
                )
            )
        return out

    async def category(self, slug: str) -> CategoryOut:
        for c in await self.categories():
            if c.slug == slug:
                return c
        raise NotFound("We couldn't find that category.", code="category_not_found")

    async def collections(
        self, products: list[Product] | None = None, preview: int = 4
    ) -> list[CollectionOut]:
        products = products if products is not None else await self.visible_products()
        live = await self.live_drop_product_ids()
        out = []
        for c in (
            await self.session.scalars(select(Collection).order_by(Collection.sort_order))
        ).all():
            tagged = sorted(
                (p for p in products if c.tag in (p.tags or [])), key=lambda p: -p.curated_score
            )
            out.append(
                CollectionOut(
                    title=c.title,
                    slug=c.slug,
                    kicker=c.kicker,
                    subtitle=c.subtitle,
                    body=c.body,
                    tag=c.tag,
                    hero_url=self.abs_url(c.hero_url),
                    product_count=len(tagged),
                    preview=[self.card(p, live) for p in tagged[:preview]],
                )
            )
        return out

    async def collection(self, slug: str) -> CollectionOut:
        for c in await self.collections(preview=0):
            if c.slug == slug:
                return c
        raise NotFound("We couldn't find that collection.", code="collection_not_found")

    def drop_status(self, d: Drop) -> str:
        if d.starts_at > self.now:
            return "upcoming"
        if d.ends_at and d.ends_at <= self.now:
            return "ended"
        return "live"

    async def drops(self, user: User | None) -> list[DropOut]:
        drops = list((await self.session.scalars(select(Drop).order_by(Drop.starts_at))).all())
        subscribed: set[uuid.UUID] = set()
        if user is not None:
            subscribed = set(
                (
                    await self.session.scalars(
                        select(DropSubscription.drop_id).where(DropSubscription.user_id == user.id)
                    )
                ).all()
            )
        live = await self.live_drop_product_ids()
        out = []
        for d in drops:
            status = self.drop_status(d)
            if status == "ended" and d.ends_at and self.now - d.ends_at > timedelta(days=7):
                continue
            visible = [p for p in d.products if status != "upcoming" and p.status == "active"]
            out.append(
                DropOut(
                    id=d.id,
                    slug=d.slug,
                    title=d.title,
                    description=d.description,
                    hero_url=self.abs_url(d.hero_url),
                    starts_at=d.starts_at,
                    ends_at=d.ends_at,
                    status=status,  # type: ignore[arg-type]
                    boutique=Ref(name=d.seller.boutique_name, slug=d.seller.slug),
                    product_count=len(d.products),
                    products=[self.card(p, live) for p in visible],
                    is_subscribed=d.id in subscribed,
                )
            )
        return out

    async def home(self, user: User | None) -> HomeOut:
        products = await self.visible_products()
        live = await self.live_drop_product_ids()
        drops = await self.drops(user)
        in_stock = [p for p in products if p.total_stock > 0]

        def top(key: Callable[[Product], Any], n: int = 12) -> list[ProductCard]:
            return [self.card(p, live) for p in sorted(in_stock, key=key)[:n]]

        counts = Counter(p.seller_id for p in products)
        featured = list(
            (
                await self.session.scalars(
                    select(SellerProfile)
                    .where(SellerProfile.status == "approved", SellerProfile.is_featured)
                    .order_by(SellerProfile.follower_count.desc())
                )
            ).all()
        )
        following = await self._following(user, [s.id for s in featured])
        collections = await self.collections(products, preview=6)
        editorial = next((c for c in collections if c.product_count), None)
        return HomeOut(
            live_drop=next((d for d in drops if d.status == "live"), None),
            upcoming_drop=next((d for d in drops if d.status == "upcoming"), None),
            categories=await self.categories(products),
            # Phase 10 personalises this rail from the Style Profile quiz.
            curated=top(lambda p: (-p.curated_score, p.slug)),
            trending=top(lambda p: (-p.wishlist_count, p.slug)),
            new_arrivals=top(
                lambda p: (-(p.published_at.timestamp() if p.published_at else 0), p.slug)
            ),
            featured_boutiques=[
                self.boutique_card(s, counts[s.id], s.id in following) for s in featured
            ],
            editorial=editorial,
        )


# ─── pure helpers (unit-tested) ────────────────────────────────────────────


def review_out(r: Review) -> ReviewOut:
    first, *rest = (r.buyer.name if r.buyer else "Queneth member").split()
    return ReviewOut(
        id=r.id,
        author=f"{first} {rest[-1][0]}." if rest else first,
        rating=r.rating,
        fit=r.fit,  # type: ignore[arg-type]
        title=r.title,
        body=r.body,
        photos=r.photos or [],
        variant_label=r.variant_label,
        seller_reply=r.seller_reply,
        helpful_count=r.helpful_count,
        verified=True,
        created_at=r.created_at,
    )


def summarize_reviews(reviews: list[Review]) -> ReviewSummary:
    count = len(reviews)
    dist = Counter(r.rating for r in reviews)
    fits = Counter(r.fit for r in reviews if r.fit)
    fit_total = sum(fits.values())
    fit = (
        {k: round(100 * fits[k] / fit_total) for k in ("small", "true", "large")}
        if fit_total
        else None
    )
    verdict = None
    if fit:
        # "Runs small / true / large" indicator from reviews (spec §9, shoes).
        verdict = max(
            [
                ("runs_small", fit["small"]),
                ("true_to_size", fit["true"]),
                ("runs_large", fit["large"]),
            ],
            key=lambda kv: kv[1],
        )[0]
    return ReviewSummary(
        average=round(sum(r.rating for r in reviews) / count, 1) if count else 0.0,
        count=count,
        distribution={str(k): dist[k] for k in range(5, 0, -1)},
        fit=fit,
        fit_verdict=verdict,  # type: ignore[arg-type]
    )


def also_love(product: Product, catalog: list[Product], n: int = 8) -> list[Product]:
    same = [p for p in catalog if p.subcategory_id == product.subcategory_id and p.id != product.id]
    rest = [
        p
        for p in catalog
        if p.category_id == product.category_id and p.id != product.id and p not in same
    ]
    return (
        sorted(same, key=lambda p: -p.curated_score)[:n]
        + sorted(rest, key=lambda p: -p.curated_score)[: max(0, n - len(same))]
    )


def complete_the_look(product: Product, catalog: list[Product], n: int = 8) -> list[Product]:
    """Pieces from *other* categories that share an edit (quiet luxury, after
    hours, citrus & sun) or the same boutique, one per subcategory for variety."""
    edits = {"quiet-luxury", "after-hours", "citrus-sun"} & set(product.tags or [])

    def score(p: Product) -> tuple[int, int]:
        shared = len(edits & set(p.tags or []))
        return (-(shared * 2 + (p.seller_id == product.seller_id)), -p.curated_score)

    picked: list[Product] = []
    seen_subs: set[uuid.UUID] = set()
    for p in sorted(
        (p for p in catalog if p.category_id != product.category_id and p.total_stock > 0),
        key=score,
    ):
        if p.subcategory_id not in seen_subs:
            picked.append(p)
            seen_subs.add(p.subcategory_id)
        if len(picked) == n:
            break
    return picked


def similar_scents(product: Product, catalog: list[Product], n: int = 8) -> list[Product]:
    if product.category.slug != "perfumes":
        return []
    mine = set((product.facet_values or {}).get("notes", []))
    family = (product.facet_values or {}).get("family", [None])[0]

    def similarity(p: Product) -> float:
        theirs = set((p.facet_values or {}).get("notes", []))
        jaccard = len(mine & theirs) / len(mine | theirs) if mine | theirs else 0
        return jaccard + (0.35 if (p.facet_values or {}).get("family", [None])[0] == family else 0)

    others = [p for p in catalog if p.category_id == product.category_id and p.id != product.id]
    return [p for p in sorted(others, key=lambda p: -similarity(p)) if similarity(p) > 0][:n]
