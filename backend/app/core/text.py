"""Small text helpers shared by services and the seed."""

import re
import unicodedata


def slugify(text: str) -> str:
    """'Maison Verdé Silk Slip' -> 'maison-verde-silk-slip'."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def sku_stem(slug: str, shop_slug: str = "", limit: int = 20) -> str:
    """'nike-air-jordan-5-black-carolina' -> 'AIR-JORDAN-5-BLACK': whole words of the
    product slug (without the shop prefix), up to `limit` characters."""
    words = slug.removeprefix(f"{shop_slug}-").split("-") if shop_slug else slug.split("-")
    stem: list[str] = []
    for w in filter(None, words):
        if stem and len("-".join([*stem, w])) > limit:
            break
        stem.append(w)
    return "-".join(stem).upper()[: max(limit, len(stem[0]) if stem else 0)]
