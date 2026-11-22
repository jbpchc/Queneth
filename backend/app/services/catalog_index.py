"""Keeps a product's denormalized listing fields in sync with its variants and
attributes. Call `refresh_denormalized` after any change to variants, price,
stock, attributes or title (seed today, the seller wizard in Phase 8)."""

from typing import Any

from app.models.catalog import Product, Variant

CLOTHING_SIZES = ["XXS", "XS", "S", "M", "L", "XL", "XXL"]
BAG_SIZES = ["Mini", "Small", "Medium", "Large"]
VOLUMES = ["30 ml", "50 ml", "100 ml"]


def size_sort_key(size: str) -> tuple[int, float, str]:
    """XXS…XXL, then numeric (EU shoe sizes), then bag sizes, then the rest."""
    if size in CLOTHING_SIZES:
        return (0, CLOTHING_SIZES.index(size), "")
    try:
        return (1, float(size.replace("EU", "").strip()), "")
    except ValueError:
        pass
    if size in BAG_SIZES:
        return (2, BAG_SIZES.index(size), "")
    if size in VOLUMES:
        return (3, VOLUMES.index(size), "")
    return (4, 0, size)


def _heel_band(cm: float) -> str:
    if cm < 1.5:
        return "Flat"
    if cm < 5:
        return "Low (1.5–5 cm)"
    if cm < 8:
        return "Mid (5–8 cm)"
    return "High (8 cm+)"


def facet_values_for(category_slug: str, attributes: dict[str, Any]) -> dict[str, list[str]]:
    """Category-specific facets (spec §9: notes/concentration for perfumes, material for bags…)."""
    a = attributes
    if category_slug == "perfumes":
        notes = sorted(
            {*a.get("top_notes", []), *a.get("heart_notes", []), *a.get("base_notes", [])}
        )
        return {"concentration": [a["concentration"]], "family": [a["family"]], "notes": notes}
    if category_slug == "bags":
        return {"material": [a["material"]], "closure": [a["closure"]]}
    if category_slug == "clothing":
        main = max(a.get("composition", [{"fiber": "", "pct": 0}]), key=lambda f: f["pct"])["fiber"]
        return {"fit": [a["fit"].capitalize()], "fabric": [main.capitalize()]} if main else {}
    if category_slug == "shoes":
        return {"heel": [_heel_band(float(a.get("heel_height_cm", 0)))], "upper": [a["upper"]]}
    if category_slug == "accessories":
        return {"material": [a["material"]]}
    return {}


def refresh_denormalized(product: Product, variants: list[Variant]) -> None:
    live = variants or []
    prices = [v.price_qc for v in live] or [0]
    product.min_price_qc = min(prices)
    product.max_price_qc = max(prices)
    cheapest = min(live, key=lambda v: v.price_qc) if live else None
    # Only a genuine markdown counts (spec §9: compare-at for real markdowns only).
    product.compare_at_qc = (
        cheapest.compare_at_qc
        if cheapest and cheapest.compare_at_qc and cheapest.compare_at_qc > cheapest.price_qc
        else None
    )
    product.total_stock = sum(v.stock for v in live)
    sizes = {v.options.get("size") or v.options.get("volume") for v in live} - {None}
    product.sizes = sorted(sizes, key=size_sort_key)  # type: ignore[arg-type]
    colors: list[str] = []
    for v in live:
        c = v.options.get("color") or v.options.get("metal")
        if c and c not in colors:
            colors.append(c)
    product.colors = colors
    category_slug = product.category.slug if product.category else ""
    try:
        product.facet_values = facet_values_for(category_slug, product.attributes or {})
    except (KeyError, TypeError, ValueError):
        # A Studio draft can have partial details; facets fill in once complete.
        product.facet_values = {}
    notes = " ".join(product.facet_values.get("notes", []))
    product.search_text = " ".join(
        filter(
            None,
            [
                product.title,
                product.brand.name if product.brand else "",
                product.seller.boutique_name if product.seller else "",
                product.subcategory.name if product.subcategory else "",
                product.category.name if product.category else "",
                " ".join(colors),
                " ".join(product.tags or []),
                notes,
            ],
        )
    ).lower()
