"""Curated royalty-free photos for the demo catalog.

Source: Unsplash (https://unsplash.com/license): free to use, including
commercially, no permission or attribution required. Unsplash+ (paid) images
were excluded, and so were photos whose subject or caption shows a real
fashion or fragrance brand, because every brand on Queneth is fictional.
Credits are in docs/CREDITS.md.

Photos are loaded from Unsplash's CDN (images.unsplash.com). Each URL carries
`fb=` — the generated SVG art for the same slot — so the frontend can swap to
it automatically when the CDN can't be reached (offline demos), see
frontend/src/components/layout/image-fallback.tsx.
"""

from urllib.parse import quote

CDN = "https://images.unsplash.com/photo-"

#: 3–5 per subcategory, each checked by eye for visible logos or labels. Products in a subcategory rotate through the pool, so
#: neighbours in a grid start on different photos.
SUBCATEGORY_PHOTOS: dict[str, list[str]] = {
    # Clothing
    "dresses": [
        "1704775990154-b87562565d4c",
        "1651047666890-8eab731ee345",
        "1642609881805-c8b7b54d97b3",
        "1704775983143-2c83798831db",
        "1773921636042-a4ed88f78feb",
    ],
    "tops": [
        "1704775983313-756dd3ac2569",
        "1790539459929-4b40e8b3f694",
        "1548778943-5bbeeb1ba6c1",
        "1779153996913-fc2565ed7e14",
    ],
    "outerwear": [
        "1589400445193-c881a4b0b38a",
        "1592327877233-90b9bfd92e48",
        "1759852909538-57985f691821",
        "1676716105765-e19fe6a01851",
    ],
    "trousers": [
        "1789110520755-058df30bf9cb",
        "1789110854083-e4752bded644",
        "1789110520143-9f54f069b43f",
        "1687825515654-23620796760c",
    ],
    "knitwear": [
        "1773747310662-e7cc9e681226",
        "1574201635302-388dd92a4c3f",
        "1758981400298-78cd18eb6793",
        "1646270968802-6bad28659329",
    ],
    "suiting": [
        "1608234808654-2a8875faa7fd",
        "1578996953841-b187dbe4bc8a",
        "1630173250799-2813d34ed14b",
        "1775680978611-4bbc221f3944",
    ],
    # Shoes
    "heels": [
        "1573100925118-870b8efc799d",
        "1596703263926-eb0762ee17e4",
        "1518049362265-d5b2a6467637",
        "1590099033615-be195f8d575c",
        "1632793039179-8d97795d20c6",
    ],
    "sneakers": [
        "1603808033192-082d6919d3e1",
        "1632497775901-50ba4637399f",
        "1780824947013-dc7e01284025",
    ],
    "loafers": [
        "1777987601447-266e128de448",
        "1760616172899-0681b97a2de3",
        "1556004583-d2aaffbba592",
        "1785357694213-15c5451a2458",
    ],
    "boots": [
        "1608256246200-53e635b5b65f",
        "1777987601423-f350ac29b3e9",
        "1763661300203-aa3e2702f510",
        "1599012307605-23a0ebe4d321",
        "1706587161985-abec97ad6af8",
    ],
    "sandals": [
        "1585120824848-8a5cd41493d2",
        "1619510331283-a46c425e48bb",
        "1562273138-f46be4ebdf33",
        "1630407332126-70ebb700976b",
        "1625563206627-7e713d1ac0a8",
    ],
    # Bags
    "totes": [
        "1624687943971-e86af76d57de",
        "1774702535771-eec0c74d6cb9",
        "1732963947955-858ad7d5e540",
        "1654707636750-ab67a11b21b7",
    ],
    "shoulder": [
        "1603219527847-24c87f552a77",
        "1604176424472-17cd740f74e9",
        "1702326626601-74d2e86922b4",
        "1732613839533-ac54fcee9d9c",
        "1594633313593-bab3825d0caf",
    ],
    "crossbody": [
        "1600857062241-98e5dba7f214",
        "1600857125164-499a823272b4",
        "1612902456551-333ac5afa26e",
        "1612902457341-ed7bf0608be3",
        "1694803121687-b87bbc61f531",
    ],
    "clutches": [
        "1749294435694-ce3c586591e6",
        "1749294435693-4f39ec7e0ab2",
        "1630484179057-75e24310e2ff",
        "1598552105309-9243044d2002",
    ],
    "backpacks": [
        "1622560480654-d96214fdc887",
        "1622560480605-d83c853bc5c3",
        "1680039211156-66c721b87625",
        "1541267732407-8f72c182cf11",
    ],
    # Accessories
    "jewelry": [
        "1617038220319-276d3cfab638",
        "1778000000743-87e855360c51",
        "1631982690223-8aa4be0a2497",
        "1569397288884-4d43d6738fbd",
        "1783541507490-edb026e2a961",
    ],
    "watches": [
        "1689287428096-7e1dcc705a5c",
        "1590995505834-e5380bba1865",
        "1792552728426-01971d490df1",
        "1758887953059-ca6f8e454207",
    ],
    "sunglasses": [
        "1584036553516-bf83210aa16c",
        "1567473810954-507d59716c25",
        "1618677366787-9727aacca7ea",
        "1653038282660-266890e79e59",
    ],
    "belts": [
        "1711443982852-b3df5c563448",
        "1734383524180-3c6f9b21e8e3",
        "1637868796504-32f45a96d5a0",
    ],
    "scarves": [
        "1606259458027-54d2a728b6ab",
        "1777795530497-205664bbd965",
        "1761369332487-777e59fa4bcf",
        "1551028442-ee84b4d3a50a",
        "1677478863154-55ecce8c7536",
    ],
    "hats": [
        "1725398807874-948f9721aad9",
        "1494028698538-2cd52a400b17",
        "1514326005837-fb4791d25e03",
        "1774082277520-dedc4977e26b",
    ],
    # Perfumes
    "women": [
        "1608721279136-cd41b752fa41",
        "1588405748880-12d1d2a59f75",
        "1598121496628-9d8b7578e290",
        "1617839400561-d55457a29da2",
    ],
    "men": [
        "1733660227168-444e3c751a1e",
        "1733660227083-12b78ad0073d",
        "1638295916768-459f6cf440bc",
    ],
    "unisex": [
        "1733660227163-01bc46e0d7d7",
        "1709662217618-83586dc9b777",
        "1705899853374-d91c048b81d2",
    ],
    "niche": [
        "1709662369957-0cbf9f8452fc",
        "1709662217659-c7966220219f",
    ],
    "gift-sets": [
        "1535683577427-740aaac4ec25",
        "1716857591457-7d7fa45199c6",
        "1622618991746-fe6004db3a47",
    ],
}

#: Boutique banners, collection and drop heroes (wide crops of store interiors).
INTERIORS = [
    "1596484552993-aec4311d3381",
    "1776000680544-ebf0989a71df",
    "1766934587163-186d20bf3d40",
    "1785860089217-5c7f62013cb9",
    "1770226415002-dbbd40327ec7",
    "1776813122119-c23f1e436098",
]


def photo(photo_id: str, *, ratio: str = "4:5", fallback: str | None = None) -> str:
    """CDN URL cropped to `ratio`; the image loader adds width/quality/format."""
    url = f"{CDN}{photo_id}?fit=crop&crop=entropy&ar={ratio}&q=80&auto=format"
    if fallback:
        url += f"&fb={quote(fallback, safe='')}"
    return url


def product_photos(subcategory: str, index: int, count: int = 3) -> list[str]:
    """`count` different photos from the subcategory pool, rotated by `index`."""
    pool = SUBCATEGORY_PHOTOS.get(subcategory, [])
    if not pool:
        return []
    return [pool[(index + k) % len(pool)] for k in range(min(count, len(pool)))]


def all_photo_ids() -> list[str]:
    ids = [p for pool in SUBCATEGORY_PHOTOS.values() for p in pool]
    return list(dict.fromkeys([*ids, *INTERIORS]))


# ─── Seed step ─────────────────────────────────────────────────────────────

ART_PREFIX = "/api/v1/catalog/art/"


async def apply_photos(session) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """Swap the generated SVG art for curated photos (idempotent).

    Per product: the three main gallery shots become photos from the
    subcategory pool (rotated, so neighbours differ); the SVG shot of the
    primary color is kept right after them, so picking that swatch still shows
    the right color. Other colors keep their SVG shots. Every photo URL carries
    its SVG as `fb=` for offline fallback.
    """
    from sqlalchemy import select

    from app.models.catalog import (
        Collection,
        Drop,
        Product,
        ProductImage,
        SellerProfile,
        Subcategory,
    )

    counts = {"products": 0, "banners": 0, "heroes": 0}
    subs = {s.id: s.slug for s in (await session.scalars(select(Subcategory))).all()}
    products = list(
        (
            await session.scalars(select(Product).order_by(Product.subcategory_id, Product.slug))
        ).all()
    )
    seen: dict[str, int] = {}
    for p in products:
        sub = subs.get(p.subcategory_id, "")
        index = seen.get(sub, 0)
        seen[sub] = index + 1
        shots = sorted(p.images, key=lambda i: i.position)
        if not shots or not shots[0].url.startswith(ART_PREFIX):
            continue  # already photographed, or a seller's own upload
        ids = product_photos(sub, index)
        if not ids:
            continue
        primary = shots[0].color
        main = [i for i in shots if i.color == primary][: len(ids)]
        rest = [i for i in shots if i not in main]
        new: list[ProductImage] = []
        for k, (img, pid) in enumerate(zip(main, ids, strict=False)):
            new.append(
                ProductImage(
                    url=photo(pid, fallback=img.url),
                    alt=f"{p.title}, photo {k + 1} of {len(ids)}",
                    position=k,
                )
            )
        if main:
            # Keep the color-correct front view for the primary swatch.
            new.append(
                ProductImage(url=main[0].url, alt=main[0].alt, position=len(new), color=primary)
            )
        for img in rest:
            new.append(ProductImage(url=img.url, alt=img.alt, position=len(new), color=img.color))
        p.images = new
        counts["products"] += 1

    for n, s in enumerate(
        (await session.scalars(select(SellerProfile).order_by(SellerProfile.created_at))).all()
    ):
        if s.banner_url and s.banner_url.startswith(ART_PREFIX):
            s.banner_url = photo(INTERIORS[n % len(INTERIORS)], ratio="3:1", fallback=s.banner_url)
            counts["banners"] += 1
    heroes = [
        *(await session.scalars(select(Collection).order_by(Collection.sort_order))).all(),
        *(await session.scalars(select(Drop).order_by(Drop.starts_at))).all(),
    ]
    for n, h in enumerate(heroes):
        if h.hero_url and h.hero_url.startswith(ART_PREFIX):
            h.hero_url = photo(
                INTERIORS[(n + 3) % len(INTERIORS)], ratio="16:9", fallback=h.hero_url
            )
            counts["heroes"] += 1
    await session.commit()
    return counts
