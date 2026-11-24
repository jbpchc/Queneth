"""Catalog seed: 5 categories, 8 boutiques, 124 products, 3 collections,
3 drops (1 live, 2 scheduled), 40+ reviews. Deterministic (seeded RNG) and
idempotent: existing rows (matched by slug/email) are left untouched."""

import random
import re
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password, utcnow
from app.core.text import slugify
from app.models import (
    Brand,
    Category,
    Collection,
    Drop,
    Product,
    ProductImage,
    Review,
    SellerProfile,
    Subcategory,
    User,
    Variant,
)
from app.schemas.catalog_attributes import attribute_json_schema, validate_attributes
from app.seed.catalog_data import (
    BOUTIQUES,
    CATEGORIES,
    COLLECTIONS,
    NIGHT_COLORS,
    PALETTE,
    PERFUMES,
    QUIET_COLORS,
    RETURN_POLICY,
    REVIEW_LINES,
    REVIEWERS,
    TEMPLATES,
    Boutique,
    Perfume,
)
from app.seed.users import DEMO_PASSWORD
from app.services.catalog_index import refresh_denormalized
from app.services.product_art import shape_for

ART = "/api/v1/catalog/art"


def round50(value: float) -> int:
    return int(round(value / 50) * 50)


def art(shape: str, n: int, hex_color: str, monogram: str) -> str:
    return f"{ART}/p/{shape}/{n}.svg?c={hex_color}&m={monogram}"


def titled(material: str, name: str) -> str:
    """'Vegetable-Tanned Leather' + 'Leather Backpack' -> 'Vegetable-Tanned Leather Backpack'."""
    if material.lower() in name.lower():
        return name
    m_words, n_words = material.split(), name.split()
    seen = {w.lower() for w in m_words}
    # Drop leading name words the material already says ("Box Calf" + "Box Crossbody").
    while len(n_words) > 1 and n_words[0].lower() in seen:
        n_words = n_words[1:]
    return " ".join([*m_words, *n_words])


def monogram(brand: str) -> str:
    letters = [w[0] for w in re.findall(r"[A-Za-z]+", brand) if w[0].isupper()]
    return "".join(letters[:2]) or brand[:2].upper()


# ─── Taxonomy, boutiques, people ───────────────────────────────────────────


async def seed_taxonomy(session: AsyncSession) -> dict[str, Category]:
    existing = {c.slug: c for c in (await session.scalars(select(Category))).all()}
    for order, (slug, name, tagline, subs) in enumerate(CATEGORIES):
        cat = existing.get(slug)
        if cat is None:
            cat = Category(slug=slug, name=name, tagline=tagline, sort_order=order)
            session.add(cat)
            existing[slug] = cat
        cat.attribute_schema = attribute_json_schema(slug)
        await session.flush()
        have = {
            s.slug
            for s in (
                await session.scalars(select(Subcategory).where(Subcategory.category_id == cat.id))
            ).all()
        }
        for i, sub in enumerate(subs):
            if slugify(sub) not in have:
                session.add(
                    Subcategory(category_id=cat.id, name=sub, slug=slugify(sub), sort_order=i)
                )
    await session.flush()
    return existing


async def _user(session: AsyncSession, email: str, name: str, roles: list[Role]) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            name=name,
            password_hash=hash_password(DEMO_PASSWORD),
            roles=[r.value for r in roles],
            email_verified_at=utcnow(),
        )
        session.add(user)
        await session.flush()
    elif Role.SELLER in roles and user.roles != [Role.SELLER.value]:
        user.roles = [Role.SELLER.value]  # one role per account: sellers don't shop
    return user


async def seed_boutiques(
    session: AsyncSession, rng: random.Random
) -> tuple[dict[str, SellerProfile], dict[str, Brand]]:
    admin = await session.scalar(select(User).where(User.email == "admin@queneth.test"))
    profiles: dict[str, SellerProfile] = {}
    brands: dict[str, Brand] = {b.slug: b for b in (await session.scalars(select(Brand))).all()}
    for b in BOUTIQUES:
        owner = await _user(session, b.owner_email, b.owner_name, [Role.SELLER])
        profile = await session.scalar(select(SellerProfile).where(SellerProfile.slug == b.slug))
        if profile is None:
            profile = SellerProfile(
                user_id=owner.id,
                boutique_name=b.name,
                slug=b.slug,
                tagline=b.tagline,
                bio=b.bio,
                return_policy=RETURN_POLICY,
                contact_email=b.owner_email,
                city=b.city,
                status="approved",
                approved_by=admin.id if admin else None,
                approved_at=utcnow() - timedelta(days=rng.randint(120, 400)),
                follower_count=rng.randint(180, 2600),
                is_featured=b.featured,
                logo_url=f"{ART}/logo.svg?c={b.color}&t={b.initials.replace('&', '')}",
                banner_url=f"{ART}/banner/{b.banner_shape}.svg?c={b.color}",
            )
            session.add(profile)
        profiles[b.slug] = profile
        for name in b.brands:
            if slugify(name) not in brands:
                brand = Brand(name=name, slug=slugify(name))
                session.add(brand)
                brands[brand.slug] = brand
    await session.flush()
    return profiles, brands


async def seed_reviewers(session: AsyncSession) -> list[User]:
    return [await _user(session, email, name, [Role.BUYER]) for email, name in REVIEWERS]


# ─── Attribute builders (validated by the per-category Pydantic models) ────

COMPOSITION = {
    "Silk": [("silk", 100)], "Crepe": [("viscose", 70), ("silk", 30)], "Linen": [("linen", 100)],
    "Satin": [("silk", 92), ("elastane", 8)], "Jersey": [("modal", 94), ("elastane", 6)],
    "Cotton": [("cotton", 100)], "Modal": [("modal", 100)], "Wool": [("wool", 100)],
    "Cotton Gabardine": [("cotton", 100)], "Bouclé": [("wool", 70), ("alpaca", 20), ("nylon", 10)],
    "Wool-Cashmere": [("wool", 80), ("cashmere", 20)], "Nylon": [("recycled nylon", 100)],
    "Denim": [("cotton", 99), ("elastane", 1)], "Cashmere": [("cashmere", 100)],
    "Merino": [("merino wool", 100)], "Mohair": [("mohair", 72), ("silk", 28)],
    "Grain de Poudre": [("wool", 100)],
}  # fmt: skip
CARE = {
    "silk": ["Dry clean", "Steam on low"], "linen": ["Machine wash cold", "Line dry", "Iron while damp"],
    "wool": ["Dry clean", "Brush after wear"], "cashmere": ["Hand wash cold", "Dry flat", "De-pill with a comb"],
    "cotton": ["Machine wash 30°C", "Iron medium"], "default": ["Dry clean only"],
}  # fmt: skip


def clothing_attrs(material: str, rng: random.Random) -> dict[str, Any]:
    comp = COMPOSITION.get(material, [("cotton", 100)])
    main = comp[0][0].split()[-1]
    return {
        "fit": rng.choice(["slim", "regular", "regular", "oversized"]),
        "composition": [{"fiber": f, "pct": p} for f, p in comp],
        "care": CARE.get(main, CARE["default"]),
        "model_height_cm": rng.randint(168, 180),
        "model_size": rng.choice(["XS", "S", "S", "M"]),
    }


HEEL_CM = {
    "heels": (5.5, 10.0),
    "sneakers": (2.0, 3.5),
    "loafers": (1.5, 3.0),
    "boots": (2.5, 7.0),
    "sandals": (0.5, 2.0),
}


def shoe_attrs(sub: str, material: str, rng: random.Random) -> dict[str, Any]:
    lo, hi = HEEL_CM[sub]
    return {
        "upper": material,
        "lining": rng.choice(["Calf leather", "Goat leather", "Cotton canvas"]),
        "sole": rng.choice(
            ["Leather, Goodyear welted", "Rubber", "Leather with rubber heel cap", "Crepe rubber"]
        ),
        "heel_height_cm": round(rng.uniform(lo, hi) * 2) / 2,
        "last": rng.choice(
            [
                "Almond toe, standard width",
                "Round toe, generous toe box",
                "Pointed toe, narrow last",
                "Square toe, relaxed fit",
            ]
        ),
    }


BAG_DIMS = {
    "totes": (38, 30, 15),
    "shoulder": (26, 18, 9),
    "crossbody": (20, 14, 6),
    "clutches": (28, 16, 4),
    "backpacks": (30, 38, 14),
}
BAG_SIZE_SCALE = {"Mini": 0.7, "Small": 0.85, "Medium": 1.0, "Large": 1.2}


def bag_attrs(sub: str, material: str, size: str, rng: random.Random) -> dict[str, Any]:
    w, h, d = (round(x * BAG_SIZE_SCALE.get(size, 1.0)) for x in BAG_DIMS[sub])
    fits = ["phone", "keys"]
    if w >= 18:
        fits += ["wallet", "sunglasses"]
    if w >= 30:
        fits += ["tablet"]
    if w >= 36 or sub == "backpacks":
        fits += ["laptop", "water bottle"]
    return {
        "width_cm": w, "height_cm": h, "depth_cm": d, "material": material,
        "hardware_finish": rng.choice(["Brushed gold", "Palladium", "Antique brass", "Gunmetal"]),
        "closure": {"totes": "Open top with magnetic snap", "clutches": "Clasp frame", "backpacks": "Drawstring and flap"}.get(sub, rng.choice(["Turn-lock", "Magnetic snap", "Zip"])),
        "strap_drop_cm": {"shoulder": 24, "crossbody": 55, "totes": 22, "backpacks": 45}.get(sub),
        "interior": rng.choice(["Suede-lined, one slip pocket", "Cotton twill lining, zip pocket", "Unlined, raw-edge finish"]),
        "fits": fits,
    }  # fmt: skip


def accessory_attrs(sub: str, material: str, rng: random.Random) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "material": material,
        "care": ["Store in the pouch provided", "Avoid perfume and water"],
    }
    if sub == "jewelry":
        attrs["stone"] = rng.choice(["South Sea pearl", "Lab-grown diamond", "None"])
        attrs["dimensions"] = rng.choice(
            ["Drop 3.5 cm", "Chain 45 cm, adjustable", "Band width 6 mm"]
        )
    if sub == "watches":
        attrs["dimensions"] = f"Case {rng.choice([34, 36, 38, 40])} mm"
        attrs["water_resistance_m"] = rng.choice([30, 50, 100, 200])
        attrs["care"] = ["Service every 5 years", "Wind weekly if not worn"]
    if sub == "sunglasses":
        attrs["dimensions"] = f"Lens {rng.choice([50, 52, 54])} mm · Bridge 19 mm"
        attrs["care"] = ["Clean with the microfibre case"]
    if sub == "scarves":
        attrs["dimensions"] = rng.choice(["90 × 90 cm", "70 × 200 cm", "55 × 55 cm"])
        attrs["care"] = ["Dry clean", "Store rolled, not folded"]
    if sub == "hats":
        attrs["care"] = ["Store crown-down", "Spot clean only"]
    return attrs


def perfume_attrs(p: Perfume) -> dict[str, Any]:
    return {
        "concentration": p.concentration, "family": p.family, "top_notes": list(p.top),
        "heart_notes": list(p.heart), "base_notes": list(p.base), "perfumer": p.perfumer,
        "longevity": p.longevity, "sillage": p.sillage, "seasons": list(p.seasons),
        "occasions": list(p.occasions),
    }  # fmt: skip


# ─── Copywriting ───────────────────────────────────────────────────────────


def describe(
    cat: str,
    sub: str,
    name: str,
    material: str,
    attrs: dict[str, Any],
    b: Boutique,
    rng: random.Random,
) -> str:
    if cat == "clothing":
        lead = f"A {attrs['fit']} {name.lower()} in {material.lower()}, cut for a clean silhouette and an easy drape."
        detail = rng.choice(
            [
                "French seams throughout and a hand-rolled hem.",
                "Horn buttons, bound seams, and a weight that hangs beautifully.",
                "Cut on the bias so it skims rather than clings.",
            ]
        )
    elif cat == "shoes":
        lead = f"The {name.lower()} on our {attrs['last'].lower()} last, in {material.lower()}."
        detail = f"{attrs['sole']} sole with a {attrs['heel_height_cm']} cm heel. Built to be resoled, not replaced."
    elif cat == "bags":
        lead = f"A {name.lower()} in {material.lower()} with {attrs['hardware_finish'].lower()} hardware."
        detail = f"{attrs['closure']}; {attrs['interior'].lower()}. Edges are hand-painted in three coats."
    elif cat == "accessories":
        lead = f"{name} in {material.lower()}, made to be worn every day and kept for decades."
        detail = rng.choice(
            [
                "Polished by hand to a soft, mirror finish.",
                "Each piece is checked under a loupe before it ships.",
                "Finished in small batches, so each one is slightly singular.",
            ]
        )
    else:
        lead = (
            f"{name}, an {attrs['family'].lower()} {attrs['concentration']} by {attrs['perfumer']}."
        )
        detail = (
            f"Opens on {', '.join(attrs['top_notes'])}; the heart turns to {', '.join(attrs['heart_notes'])}; "
            f"it dries down to {', '.join(attrs['base_notes'])}."
        )
    closing = f"Made for {b.name} in {b.city}. {b.tagline}"
    return f"{lead} {detail}\n\n{closing}"


# ─── Products ──────────────────────────────────────────────────────────────


def _stock(rng: random.Random) -> int:
    return rng.choices([0, 1, 2, 3, 5, 8, 12], weights=[6, 6, 8, 18, 26, 22, 14])[0]


def _condition(sub: str, rng: random.Random) -> str:
    preloved = 0.3 if sub in {"shoulder", "watches", "jewelry", "totes"} else 0.08
    roll = rng.random()
    if roll < preloved * 0.65:
        return "preloved_excellent"
    if roll < preloved:
        return "preloved_good"
    return "new"


def _authenticity(condition: str, brand: str) -> str:
    if condition == "new":
        return f"Sourced directly from {brand}. Ships with the house dust bag, care card and certificate."
    return (
        "Authenticated by Queneth's in-house specialists: hardware, stitching and date stamps checked "
        "against the house's records. Any signs of wear are noted in the photos."
    )


def _tags(
    cat: str, sub: str, color: str, material: str, extra: tuple[str, ...], family: str | None = None
) -> list[str]:
    tags = {sub, slugify(material)}
    tags.update(extra)
    if color in QUIET_COLORS and cat in {"clothing", "bags"} | (
        {"shoes"} if sub == "loafers" else set()
    ):
        tags.add("quiet-luxury")
    if (
        color in NIGHT_COLORS and sub in {"heels", "clutches", "jewelry", "dresses", "watches"}
    ) or family in {"Amber", "Leather"}:
        tags.add("after-hours")
    if family in {"Citrus", "Fresh"} or (
        color in {"Citron", "Natural", "Terracotta"} and sub in {"sandals", "hats", "totes"}
    ):
        tags.add("citrus-sun")
    return sorted(tags)


async def _add_product(
    session: AsyncSession,
    *,
    rng: random.Random,
    category: Category,
    sub: Subcategory,
    boutique: Boutique,
    seller: SellerProfile,
    brand: Brand,
    title: str,
    material: str,
    attrs: dict[str, Any],
    colors: list[str],
    variants: list[dict[str, Any]],
    tags: list[str],
    color_hex: dict[str, str],
    published_days_ago: int,
    taken: set[str],
) -> Product:
    slug = slugify(f"{brand.name} {title}")
    while slug in taken:
        slug = f"{slug}-{rng.randint(2, 99)}"
    taken.add(slug)
    condition = _condition(sub.slug, rng)
    product = Product(
        seller_id=seller.id,
        brand_id=brand.id,
        category_id=category.id,
        subcategory_id=sub.id,
        title=title,
        slug=slug,
        description=describe(category.slug, sub.slug, title, material, attrs, boutique, rng),
        condition=condition,
        authenticity_note=_authenticity(condition, brand.name),
        attributes=validate_attributes(category.slug, attrs),
        tags=tags,
        status="active",
        published_at=utcnow() - timedelta(days=published_days_ago, hours=rng.randint(0, 20)),
        curated_score=rng.randint(40, 92) + (8 if "quiet-luxury" in tags else 0),
        wishlist_count=int(rng.paretovariate(1.4) * 6),
        view_count=rng.randint(80, 2400),
    )
    product.seller, product.brand, product.category, product.subcategory = (
        seller,
        brand,
        category,
        sub,
    )
    shape = shape_for(sub.slug, slug)
    mono = monogram(brand.name)
    primary = colors[0]
    images = [
        ProductImage(
            url=art(shape, n, color_hex[primary], mono),
            alt=f"{title} in {primary}, {view}",
            position=i,
            color=primary,
        )
        for i, (n, view) in enumerate(
            [(1, "front view"), (2, "detail close-up"), (3, "styled on a plinth")]
        )
    ]
    for j, c in enumerate(colors[1:3]):
        images.append(
            ProductImage(
                url=art(shape, 1, color_hex[c], mono),
                alt=f"{title} in {c}, front view",
                position=3 + j,
                color=c,
            )
        )
    product.images = images
    variant_rows = [
        Variant(
            sku=f"QN-{mono}-{len(taken):03}-{k:02}",
            options=v["options"],
            price_qc=v["price"],
            compare_at_qc=v.get("compare_at"),
            stock=_stock(rng),
            low_stock_threshold=3,
            position=k,
        )
        for k, v in enumerate(variants)
    ]
    if all(v.stock == 0 for v in variant_rows):
        variant_rows[0].stock = 4
    product.variants = variant_rows
    refresh_denormalized(product, variant_rows)
    session.add(product)
    return product


async def seed_products(
    session: AsyncSession,
    rng: random.Random,
    categories: dict[str, Category],
    profiles: dict[str, SellerProfile],
    brands: dict[str, Brand],
) -> list[Product]:
    taken = set((await session.scalars(select(Product.slug))).all())
    boutique_by_slug = {b.slug: b for b in BOUTIQUES}
    products: list[Product] = []
    for cat_slug, _, _, subs in CATEGORIES:
        category = categories[cat_slug]
        sub_rows = {
            s.slug: s
            for s in (
                await session.scalars(
                    select(Subcategory).where(Subcategory.category_id == category.id)
                )
            ).all()
        }
        if cat_slug == "perfumes":
            continue
        for sub_name in subs:
            sub_slug = slugify(sub_name)
            sub = sub_rows[sub_slug]
            tpl = TEMPLATES[sub_slug]
            makers = [b for b in BOUTIQUES if sub_slug in b.specialties]
            for i, name in enumerate(tpl.names):
                material = tpl.materials[i % len(tpl.materials)]
                b = makers[i % len(makers)]
                brand = brands[slugify(b.brands[i % len(b.brands)])]
                colors = rng.sample(
                    list(tpl.colors), k=min(len(tpl.colors), rng.choice([1, 2, 2, 3]))
                )
                base = round50(rng.uniform(*tpl.price))
                markdown = rng.random() < 0.12
                variants: list[dict[str, Any]] = []
                size_key = "size"
                if cat_slug == "clothing":
                    order = ["XXS", "XS", "S", "M", "L", "XL", "XXL"]
                    start = rng.randint(0, 2)
                    sizes = order[start : start + 5]
                    attrs = clothing_attrs(material, rng)
                    title = titled(material, name)
                elif cat_slug == "shoes":
                    lo = 35 if sub_slug in {"heels", "sandals"} else 37
                    sizes = [str(s) for s in range(lo, lo + 7)]
                    attrs = shoe_attrs(sub_slug, material, rng)
                    title = titled(material, name) if sub_slug != "sandals" else name
                elif cat_slug == "bags":
                    sizes = {
                        "totes": ["Medium", "Large"],
                        "shoulder": ["Mini", "Medium"],
                        "crossbody": ["Small"],
                        "clutches": [],
                        "backpacks": ["Medium"],
                    }[sub_slug]
                    attrs = bag_attrs(sub_slug, material, (sizes or ["Medium"])[0], rng)
                    title = titled(material, name)
                else:
                    sizes = {
                        "jewelry": ["5", "6", "7", "8"] if "Ring" in name else [],
                        "belts": ["75 cm", "80 cm", "85 cm", "90 cm"],
                        "hats": ["S", "M", "L"],
                    }.get(sub_slug, [])
                    attrs = accessory_attrs(sub_slug, material, rng)
                    title = name
                    if sub_slug in {"jewelry", "watches"}:
                        size_key = "size"
                axis = "metal" if sub_slug in {"jewelry", "watches"} else "color"
                for c in colors:
                    for s in sizes or [None]:
                        mult = BAG_SIZE_SCALE.get(s, 1.0) if cat_slug == "bags" and s else 1.0
                        price = round50(base * mult)
                        opts = {axis: c}
                        if s:
                            opts[size_key] = s
                        if cat_slug == "shoes":
                            opts["width"] = "Standard"
                        variants.append(
                            {
                                "options": opts,
                                "price": price,
                                "compare_at": round50(price * 1.25) if markdown else None,
                            }
                        )
                tags = _tags(cat_slug, sub_slug, colors[0], material, tpl.extra_tags)
                products.append(
                    await _add_product(
                        session, rng=rng, category=category, sub=sub, boutique=b, seller=profiles[b.slug],
                        brand=brand, title=title, material=material, attrs=attrs, colors=colors,
                        variants=variants, tags=tags, color_hex=PALETTE,
                        published_days_ago=rng.randint(3, 160), taken=taken,
                    )
                )  # fmt: skip
    # Perfumes: hand-written library.
    category = categories["perfumes"]
    sub_rows = {
        s.slug: s
        for s in (
            await session.scalars(select(Subcategory).where(Subcategory.category_id == category.id))
        ).all()
    }
    for i, p in enumerate(PERFUMES):
        b = boutique_by_slug[p.boutique]
        brand = brands[slugify(b.brands[0 if i % 3 else min(1, len(b.brands) - 1)])]
        volumes = (
            [("30 ml", 0.62), ("50 ml", 1.0), ("100 ml", 1.55)]
            if p.sub != "gift-sets"
            else [("5 × 10 ml", 1.0)]
        )
        markdown = rng.random() < 0.1
        variants = [
            {
                "options": {"volume": v},
                "price": round50(p.price_50 * m),
                "compare_at": round50(p.price_50 * m * 1.2) if markdown else None,
            }
            for v, m in volumes
        ]
        attrs = perfume_attrs(p)
        tags = _tags("perfumes", p.sub, "", p.family, (), p.family)
        products.append(
            await _add_product(
                session, rng=rng, category=category, sub=sub_rows[p.sub], boutique=b, seller=profiles[b.slug],
                brand=brand, title=p.name, material=p.family, attrs=attrs, colors=[p.name],
                variants=variants, tags=tags, color_hex={p.name: p.color},
                published_days_ago=rng.randint(3, 140), taken=taken,
            )
        )  # fmt: skip
    # Perfume "colors" were only used to tint the bottle art; they aren't a variant axis.
    for prod in products:
        if prod.category.slug == "perfumes":
            prod.colors = []
            for img in prod.images:
                img.color = None
    # UX: Choice Overload — one Connoisseur's pick per subcategory.
    best: dict[Any, Product] = {}
    for prod in products:
        cur = best.get(prod.subcategory_id)
        if cur is None or prod.curated_score > cur.curated_score:
            best[prod.subcategory_id] = prod
    for prod in best.values():
        prod.is_connoisseur_pick = True
    await session.flush()
    return products


async def seed_reviews(
    session: AsyncSession, rng: random.Random, products: list[Product], reviewers: list[User]
) -> int:
    count = 0
    candidates = sorted(products, key=lambda p: -p.wishlist_count)[:60]
    for prod in candidates:
        n = rng.choice([0, 1, 1, 2, 3]) if count < 60 else 0
        authors = rng.sample(reviewers, k=n)
        ratings: list[int] = []
        for author in authors:
            title, body = rng.choice(REVIEW_LINES[prod.category.slug])
            rating = rng.choices([5, 4, 3, 2], weights=[55, 30, 12, 3])[0]
            fit = None
            if prod.category.slug in {"clothing", "shoes"}:
                fit = (
                    "small"
                    if "small" in body.lower() or "size up" in title.lower()
                    else rng.choices(["true", "small", "large"], weights=[60, 25, 15])[0]
                )
            label_bits = [prod.sizes[len(prod.sizes) // 2]] if prod.sizes else []
            label_bits += prod.colors[:1]
            review = Review(
                product_id=prod.id, buyer_id=author.id, rating=rating, fit=fit, title=title, body=body,
                photos=[], variant_label=" · ".join(label_bits) or None, status="published",
                helpful_count=rng.randint(0, 24),
            )  # fmt: skip
            review.created_at = (prod.published_at or utcnow()) + timedelta(days=rng.randint(4, 30))
            if rng.random() < 0.3:
                review.seller_reply = f"Thank you, {author.name.split()[0]}. It means a lot to the studio. — {prod.seller.boutique_name}"
                review.seller_replied_at = review.created_at + timedelta(days=1)
            session.add(review)
            ratings.append(rating)
            count += 1
        if ratings:
            prod.rating_count = len(ratings)
            prod.rating_avg = round(sum(ratings) / len(ratings), 2)
    await session.flush()
    return count


async def seed_collections(session: AsyncSession) -> None:
    have = set((await session.scalars(select(Collection.slug))).all())
    for i, (slug, title, kicker, tag, subtitle, body, color, shape, featured) in enumerate(
        COLLECTIONS
    ):
        if slug in have:
            continue
        session.add(
            Collection(
                slug=slug, title=title, kicker=kicker, tag=tag, subtitle=subtitle, body=body,
                hero_url=f"{ART}/banner/{shape}.svg?c={PALETTE[color]}", is_featured=featured, sort_order=i,
            )
        )  # fmt: skip


async def seed_drops(
    session: AsyncSession, products: list[Product], profiles: dict[str, SellerProfile]
) -> None:
    if await session.scalar(select(func.count()).select_from(Drop)):
        return
    now = utcnow().replace(minute=0, second=0, microsecond=0)
    by_title = {p.title: p for p in products}

    def pick(seller: str, sub: str, k: int) -> list[Product]:
        return [
            p for p in products if p.seller_id == profiles[seller].id and p.subcategory.slug == sub
        ][:k]

    plans = [
        ("night-garden", "Night Garden", "nocturne-parfums", now - timedelta(days=2), now + timedelta(days=5),
         "Three florals composed to open after sunset: sampaguita, ylang-ylang and Ilaya rose, macerated for six weeks.",
         [by_title[t] for t in ("Sampaguita Absolue", "Ylang Mer", "Rose Ilaya") if t in by_title], "perfume-1", "1f2a44"),
        ("the-marikina-last-vol-ii", "The Marikina Last, Vol. II", "obra-leather", now + timedelta(days=3, hours=11), None,
         "A new last, three silhouettes. Goodyear-welted in Marikina and numbered by hand.",
         pick("obra-leather", "boots", 2) + pick("obra-leather", "loafers", 1), "boots", "4b2e24"),
        ("kintsugi-gold", "Kintsugi Gold", "kintsu-jewels", now + timedelta(days=9, hours=11), None,
         "Recycled gold, seamed like mended porcelain. Twelve pieces of each, then never again.",
         pick("kintsu-jewels", "jewelry", 3), "necklace", "c9a44c"),
    ]  # fmt: skip
    for slug, title, seller, starts, ends, desc, items, shape, color in plans:
        for p in items:
            p.published_at = starts  # products go live with the drop (real, not fake, countdowns)
            if "new-drop" not in p.tags:
                p.tags = sorted({*p.tags, "new-drop"})
        session.add(
            Drop(
                seller_id=profiles[seller].id, title=title, slug=slug, description=desc,
                hero_url=f"{ART}/banner/{shape}.svg?c={color}", starts_at=starts, ends_at=ends, products=items,
            )
        )  # fmt: skip


async def seed_catalog(session: AsyncSession) -> dict[str, int]:
    rng = random.Random(2026)
    categories = await seed_taxonomy(session)
    profiles, brands = await seed_boutiques(session, rng)
    reviewers = await seed_reviewers(session)
    await seed_collections(session)
    created = {"products": 0, "reviews": 0}
    if not await session.scalar(select(func.count()).select_from(Product)):
        products = await seed_products(session, rng, categories, profiles, brands)
        created["products"] = len(products)
        created["reviews"] = await seed_reviews(session, rng, products, reviewers)
        await seed_drops(session, products, profiles)
    await session.commit()
    return created
