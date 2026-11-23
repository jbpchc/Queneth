"""Three named sellers with their own pieces: Nike, Penshoppe and Bench.

Opt-in (`python -m app.seed --brands`, or `scripts/run_demo.py --brands`).
Each is an approved boutique with its own seller account, so every piece is
tied to its seller and listed under that brand. Photos are linked from
Unsplash (free license); the Nike shots show Nike products, while Penshoppe
and Bench use plain, logo-free basics. Idempotent: re-running adds nothing.
"""

import random
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password, utcnow
from app.core.text import slugify
from app.models import User
from app.models.catalog import (
    Brand,
    Category,
    Product,
    ProductImage,
    SellerProfile,
    Subcategory,
    Variant,
)
from app.schemas.catalog_attributes import validate_attributes
from app.seed.catalog_data import RETURN_POLICY
from app.seed.photos import photo
from app.seed.users import DEMO_PASSWORD
from app.seed.wallet import DEMO_PIN
from app.services import wallet_service as ws
from app.services.catalog_index import refresh_denormalized

ART = "/api/v1/catalog/art"
TEES = ["XS", "S", "M", "L", "XL"]
WAIST = ["28", "30", "32", "34", "36"]
SHOES = ["7", "8", "9", "10", "11"]


@dataclass(frozen=True)
class Seller:
    slug: str
    name: str
    email: str
    owner: str
    city: str
    tagline: str
    bio: str
    color: str
    initials: str
    banner: str
    featured: bool = True


@dataclass(frozen=True)
class Item:
    title: str
    category: str
    sub: str
    price: int
    photos: list[str]
    colors: list[str]
    description: str
    attrs: dict[str, Any]
    sizes: list[str] | None = None
    tags: list[str] = field(default_factory=list)
    compare_at: int | None = None


SELLERS = [
    Seller(
        slug="nike",
        name="Nike",
        email="nike@queneth.test",
        owner="Nike Store Manila",
        city="Taguig",
        tagline="Just do it.",
        bio="Performance and sportswear: running, training and the classics, shipped from Manila.",
        color="111111",
        initials="N",
        banner="1617611413968-537a2ba4986d",
    ),
    Seller(
        slug="penshoppe",
        name="Penshoppe",
        email="penshoppe@queneth.test",
        owner="Penshoppe Online",
        city="Pasay",
        tagline="Everyday essentials, made to move with you.",
        bio="Casual basics and denim for every day: tees, hoodies, jeans and accessories.",
        color="1f3a5f",
        initials="P",
        banner="1489987707025-afc232f7ea0f",
    ),
    Seller(
        slug="bench",
        name="Bench",
        email="bench@queneth.test",
        owner="Bench Online",
        city="Quezon City",
        tagline="Quality basics, Filipino-made since 1987.",
        bio="Polos, knits, denim and the pieces you reach for most, in easy fits and fabrics.",
        color="b3202a",
        initials="B",
        banner="1620799140188-3b2a02fd9a77",
    ),
]


def cotton(fit: str = "regular", pct: int = 100, other: str | None = None) -> dict[str, Any]:
    comp = [{"fiber": "cotton", "pct": pct}] + (
        [{"fiber": other, "pct": 100 - pct}] if other else []
    )
    return {
        "fit": fit,
        "composition": comp,
        "care": ["Machine wash cold", "Do not bleach", "Tumble dry low"],
    }


def shoe(upper: str, sole: str = "Rubber", heel: float = 3.0) -> dict[str, Any]:
    return {
        "upper": upper,
        "lining": "Textile",
        "sole": sole,
        "heel_height_cm": heel,
        "last": "Round toe, standard width",
    }


ITEMS: dict[str, list[Item]] = {
    "nike": [
        Item(
            "Air Force 1 '07",
            "shoes",
            "sneakers",
            5_895,
            ["1600269452121-4f2416e55c28"],
            ["White"],
            "The basketball original in crisp leather, with Air cushioning under the heel and the stitched overlays it's known for.",
            shoe("Leather"),
            SHOES,
            ["streetwear"],
        ),
        Item(
            "Air Force 1 Low Flax",
            "shoes",
            "sneakers",
            6_495,
            ["1549298916-b41d501d3772"],
            ["Wheat"],
            "The low-top classic in a warm wheat nubuck with a gum sole.",
            shoe("Nubuck", "Gum rubber"),
            SHOES,
            ["streetwear"],
        ),
        Item(
            "Air Max 90",
            "shoes",
            "sneakers",
            7_395,
            ["1600185365483-26d7a4cc7519", "1600185365926-3a2ce3cdb9eb"],
            ["White"],
            "Visible Air in the heel, a waffle outsole and layered suede-and-mesh panels.",
            shoe("Mesh and suede"),
            SHOES,
            ["streetwear"],
        ),
        Item(
            "Air Jordan 1 Mid",
            "shoes",
            "sneakers",
            7_195,
            ["1597045566677-8cf032ed6634"],
            ["Black"],
            "The mid-top Jordan 1 in leather with an encapsulated Air unit.",
            shoe("Leather", heel=3.5),
            SHOES,
            ["streetwear"],
        ),
        Item(
            "Free RN Flyknit",
            "shoes",
            "sneakers",
            5_495,
            ["1542291026-7eec264c27ff"],
            ["Red"],
            "A barefoot-feel runner: a sock-like Flyknit upper over a flexible, grooved sole.",
            shoe("Flyknit", heel=2.5),
            SHOES,
            ["running"],
            compare_at=6_295,
        ),
        Item(
            "Zoom Superrep",
            "shoes",
            "sneakers",
            6_895,
            ["1606107557195-0e29a4b5b4aa"],
            ["Volt"],
            "Made for circuits and HIIT, with Zoom Air under the forefoot and a wide, stable heel.",
            shoe("Engineered mesh", heel=3.0),
            SHOES,
            ["training"],
        ),
        Item(
            "Metcon Training Shoe",
            "shoes",
            "sneakers",
            6_295,
            ["1605408499391-6368c628ef42"],
            ["Black"],
            "A flat, stable heel for lifting and a grippy rubber wrap for rope climbs.",
            shoe("Mesh", heel=2.0),
            SHOES,
            ["training"],
        ),
        Item(
            "Air Max Pastel",
            "shoes",
            "sneakers",
            7_595,
            ["1595950653106-6c9ebd614d3a"],
            ["Pink"],
            "Soft pastel panels over a full-length Air sole.",
            shoe("Mesh and synthetic leather"),
            SHOES,
            ["streetwear"],
        ),
        Item(
            "Sportswear Club Hoodie",
            "clothing",
            "tops",
            3_295,
            ["1611886658579-83fc4eae8176"],
            ["Teal"],
            "Brushed-back fleece with a roomy hood, kangaroo pocket and the embroidered logo.",
            cotton("regular", 80, "polyester"),
            TEES,
            ["streetwear"],
        ),
        Item(
            "Air Graphic Tee",
            "clothing",
            "tops",
            1_595,
            ["1585032767761-878270336a0b"],
            ["Sky blue"],
            "A soft cotton jersey tee with the Air graphic across the chest.",
            cotton(),
            TEES,
            ["streetwear"],
        ),
        Item(
            "Windrunner Jacket",
            "clothing",
            "outerwear",
            4_995,
            ["1606105961732-6332674f4ee6"],
            ["White"],
            "The chevron-panelled windbreaker in lightweight woven fabric, with a stowaway hood.",
            {
                "fit": "regular",
                "composition": [{"fiber": "polyester", "pct": 100}],
                "care": ["Machine wash cold", "Do not iron"],
            },
            TEES,
            ["streetwear"],
        ),
        Item(
            "Heritage86 Cap",
            "accessories",
            "hats",
            1_395,
            ["1556793521-ec4b34e6545e"],
            ["White"],
            "An unstructured six-panel cap with an adjustable strap and embroidered Swoosh.",
            {"material": "Cotton twill", "care": ["Spot clean only"]},
            None,
            ["streetwear"],
        ),
        Item(
            "Brasilia Backpack",
            "bags",
            "backpacks",
            1_895,
            ["1573878930082-8f0fe89a2393"],
            ["Red"],
            "A durable everyday backpack with a padded laptop sleeve and a zip front pocket.",
            {
                "width_cm": 30,
                "height_cm": 46,
                "depth_cm": 16,
                "material": "Polyester",
                "hardware_finish": "Matte black",
                "closure": "Zip",
                "strap_drop_cm": 45,
                "interior": "Padded laptop sleeve",
                "fits": ["phone", "keys", "wallet", "laptop", "water bottle"],
            },
            None,
            ["school"],
        ),
    ],
    "penshoppe": [
        Item(
            "Basic Crew Neck Tee",
            "clothing",
            "tops",
            499,
            ["1581655353564-df123a1eb820", "1521572163474-6864f9cf17ab"],
            ["White"],
            "A soft, mid-weight cotton tee with a ribbed crew neck. The one you'll wear on repeat.",
            cotton(),
            TEES,
            ["basics"],
        ),
        Item(
            "Relaxed Fit Tee",
            "clothing",
            "tops",
            599,
            ["1562157873-818bc0726f68"],
            ["Black", "Navy", "Red"],
            "A relaxed cut with dropped shoulders in cotton jersey.",
            cotton("oversized"),
            TEES,
            ["basics"],
        ),
        Item(
            "Oversized Hoodie",
            "clothing",
            "tops",
            1_299,
            ["1578768079052-aa76e52ff62e", "1611817757591-c3f345024273"],
            ["Taupe"],
            "Heavyweight fleece in an oversized fit, with a double-layer hood.",
            cotton("oversized", 80, "polyester"),
            TEES,
            ["basics"],
            compare_at=1_599,
        ),
        Item(
            "Denim Trucker Jacket",
            "clothing",
            "outerwear",
            1_999,
            ["1611312449408-fcece27cdbb7", "1543076447-215ad9ba6923"],
            ["Dark wash"],
            "A classic trucker in rigid denim with chest flap pockets and a corduroy collar.",
            cotton(),
            TEES,
            ["denim"],
        ),
        Item(
            "Straight Leg Jeans",
            "clothing",
            "trousers",
            1_499,
            ["1602293589930-45aad59ba3ab", "1631112230741-446762ee05ac"],
            ["Light wash"],
            "Mid-rise, straight through the leg, in comfort-stretch denim.",
            cotton("regular", 98, "elastane"),
            WAIST,
            ["denim"],
        ),
        Item(
            "High Waist Mom Jeans",
            "clothing",
            "trousers",
            1_599,
            ["1598554747436-c9293d6a588f"],
            ["Light wash"],
            "A high rise and a relaxed, tapered leg.",
            cotton("regular", 99, "elastane"),
            WAIST,
            ["denim"],
        ),
        Item(
            "Cargo Joggers",
            "clothing",
            "trousers",
            1_199,
            ["1473966968600-fa801b869a1a"],
            ["Khaki"],
            "Elastic-cuff joggers with roomy cargo pockets.",
            cotton(),
            TEES,
            ["basics"],
        ),
        Item(
            "Bucket Hat",
            "accessories",
            "hats",
            499,
            ["1627683566270-bf7e75dfec0a"],
            ["Olive"],
            "A soft cotton bucket hat with a short, packable brim.",
            {"material": "Cotton twill", "care": ["Hand wash", "Air dry"]},
            None,
            ["basics"],
        ),
        Item(
            "Mini Crossbody Bag",
            "bags",
            "crossbody",
            899,
            ["1620786514684-ff35b5aae55e", "1620786514669-06e2340fce71"],
            ["Black"],
            "A compact crossbody with an adjustable strap and a zip top.",
            {
                "width_cm": 20,
                "height_cm": 14,
                "depth_cm": 6,
                "material": "Faux leather",
                "hardware_finish": "Gunmetal",
                "closure": "Zip",
                "strap_drop_cm": 55,
                "interior": "One slip pocket",
                "fits": ["phone", "keys", "wallet"],
            },
            None,
            ["basics"],
        ),
    ],
    "bench": [
        Item(
            "Classic Crew Tee",
            "clothing",
            "tops",
            399,
            ["1622445275463-afa2ab738c34"],
            ["Grey"],
            "Bench's everyday crew neck in soft combed cotton.",
            cotton(),
            TEES,
            ["basics"],
        ),
        Item(
            "Pique Polo",
            "clothing",
            "tops",
            799,
            ["1671438118097-479e63198629", "1586363104862-3a5e2ab60d99"],
            ["White", "Coral", "Green"],
            "A breathable cotton pique polo with a two-button placket.",
            cotton(),
            TEES,
            ["basics"],
        ),
        Item(
            "Pullover Hoodie",
            "clothing",
            "tops",
            1_199,
            ["1564557287817-3785e38ec1f5", "1650287052182-a13d8245c927"],
            ["Brown"],
            "Midweight fleece with a lined hood and ribbed cuffs.",
            cotton("regular", 70, "polyester"),
            TEES,
            ["basics"],
            compare_at=1_499,
        ),
        Item(
            "Light Wash Denim Jacket",
            "clothing",
            "outerwear",
            1_799,
            ["1537465978529-d23b17165b3b", "1555583743-991174c11425"],
            ["Light wash"],
            "A faded trucker jacket that works over everything.",
            cotton(),
            TEES,
            ["denim"],
        ),
        Item(
            "Utility Cargo Pants",
            "clothing",
            "trousers",
            1_299,
            ["1552902865-b72c031ac5ea", "1548883354-7622d03aca27"],
            ["Black"],
            "Relaxed cargo pants in cotton twill with six pockets.",
            cotton("oversized"),
            WAIST,
            ["basics"],
        ),
        Item(
            "Chunky Knit Sweater",
            "clothing",
            "knitwear",
            1_099,
            ["1574201635302-388dd92a4c3f", "1601379327928-bedfaf9da2d0"],
            ["Cream"],
            "A cosy cable knit in a soft cotton-acrylic blend.",
            {
                "fit": "oversized",
                "composition": [{"fiber": "cotton", "pct": 60}, {"fiber": "acrylic", "pct": 40}],
                "care": ["Hand wash cold", "Dry flat"],
            },
            TEES,
            ["basics"],
        ),
        Item(
            "Canvas Tote",
            "bags",
            "totes",
            599,
            ["1574365569389-a10d488ca3fb", "1630381260512-e3fe55c11973"],
            ["Natural"],
            "A sturdy cotton canvas tote with long handles.",
            {
                "width_cm": 38,
                "height_cm": 40,
                "depth_cm": 10,
                "material": "Cotton canvas",
                "hardware_finish": "None",
                "closure": "Open top",
                "strap_drop_cm": 25,
                "interior": "Unlined",
                "fits": ["phone", "keys", "wallet", "tablet", "laptop"],
            },
            None,
            ["basics"],
        ),
        Item(
            "Leather Belt",
            "accessories",
            "belts",
            699,
            ["1664285612706-b32633c95820", "1664286074176-5206ee5dc878"],
            ["Brown"],
            "Full-grain leather with a brushed metal buckle.",
            {
                "material": "Leather",
                "dimensions": "Width 3.5 cm",
                "care": ["Wipe clean", "Condition occasionally"],
            },
            ["S", "M", "L"],
            ["basics"],
        ),
    ],
}


async def _owner(session: AsyncSession, s: Seller) -> User:
    user = await session.scalar(select(User).where(User.email == s.email))
    if user is None:
        user = User(
            email=s.email,
            name=s.owner,
            password_hash=hash_password(DEMO_PASSWORD),
            roles=[Role.BUYER.value, Role.SELLER.value],
            email_verified_at=utcnow(),
        )
        session.add(user)
        await session.flush()
    wallet = await ws.user_wallet(session, user.id)
    if wallet.pin_hash is None:
        wallet.pin_hash = hash_password(DEMO_PIN)
    await ws.grant_welcome(session, user)
    return user


async def seed_brand_sellers(session: AsyncSession) -> dict[str, int]:
    rng = random.Random(2026)
    await ws.ensure_system_wallets(session)
    admin = await session.scalar(select(User).where(User.email == "admin@queneth.test"))
    cats = {c.slug: c for c in (await session.scalars(select(Category))).all()}
    subs = {(s.category_id, s.slug): s for s in (await session.scalars(select(Subcategory))).all()}
    added = {"sellers": 0, "products": 0}
    for s in SELLERS:
        owner = await _owner(session, s)
        profile = await session.scalar(select(SellerProfile).where(SellerProfile.slug == s.slug))
        if profile is None:
            profile = SellerProfile(
                user_id=owner.id,
                boutique_name=s.name,
                slug=s.slug,
                tagline=s.tagline,
                bio=s.bio,
                return_policy=RETURN_POLICY,
                contact_email=s.email,
                city=s.city,
                status="approved",
                approved_by=admin.id if admin else None,
                approved_at=utcnow(),
                is_featured=s.featured,
                logo_url=f"{ART}/logo.svg?c={s.color}&t={s.initials}",
                banner_url=photo(s.banner, ratio="3:1"),
            )
            session.add(profile)
            await session.flush()
            added["sellers"] += 1
        brand = await session.scalar(select(Brand).where(Brand.slug == slugify(s.name)))
        if brand is None:
            brand = Brand(name=s.name, slug=slugify(s.name))
            session.add(brand)
            await session.flush()
        for n, it in enumerate(ITEMS[s.slug]):
            slug = slugify(f"{s.name} {it.title}")
            if await session.scalar(select(Product.id).where(Product.slug == slug)):
                continue
            cat = cats[it.category]
            sub = subs[(cat.id, it.sub)]
            p = Product(
                seller_id=profile.id,
                brand_id=brand.id,
                category_id=cat.id,
                subcategory_id=sub.id,
                title=it.title,
                slug=slug,
                description=it.description,
                condition="new",
                authenticity_note=f"Sold by {s.name}'s official store. Brand new, with tags.",
                attributes=validate_attributes(it.category, it.attrs),
                tags=sorted({it.sub, *it.tags}),
                status="active",
                published_at=utcnow() - timedelta(days=n, hours=rng.randint(0, 20)),
                curated_score=rng.randint(55, 90),
                wishlist_count=rng.randint(3, 60),
                view_count=rng.randint(100, 3000),
            )
            p.seller, p.brand, p.category, p.subcategory = profile, brand, cat, sub
            p.images = [
                ProductImage(url=photo(pid), alt=f"{s.name} {it.title}, view {i + 1}", position=i)
                for i, pid in enumerate(it.photos)
            ]
            variants = []
            for color in it.colors:
                for size in it.sizes or [None]:
                    opts = {"color": color} | ({"size": size} if size else {})
                    k = len(variants)
                    variants.append(
                        Variant(
                            sku=f"{s.initials}-{slug[-12:].upper()}-{k:02}",
                            options=opts,
                            price_qc=it.price,
                            compare_at_qc=it.compare_at,
                            stock=rng.choice([3, 5, 8, 12, 20]),
                            low_stock_threshold=3,
                            position=k,
                        )
                    )
            p.variants = variants
            refresh_denormalized(p, variants)
            session.add(p)
            added["products"] += 1
    await session.commit()
    return added
