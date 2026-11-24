"""Named product colors and their swatch hex values (shared by seed, facets and art)."""

PALETTE: dict[str, str] = {
    "Ivory": "f2ebdd", "Noir": "1c1a1d", "Camel": "b08457", "Bordeaux": "6b1e2e",
    "Sage": "9caf88", "Blush": "e8b4b8", "Sand": "d8c3a5", "Chocolate": "4b2e24",
    "Navy": "1f2a44", "Olive": "6b6b3a", "Cobalt": "2f4bff", "Terracotta": "c0603e",
    "Lilac": "c9b6ff", "Citron": "d9d36b", "Silver": "c0c0c8", "Gold": "c9a44c",
    "Rose Gold": "b76e79", "Tortoise": "6e4a2e", "Natural": "d9c49b", "Ecru": "e9e1cf",
    # Everyday names used by the brand stores (Nike, Bench, Penshoppe)
    "Black": "151515", "White": "f7f7f5", "Grey": "8e8e8e", "Light grey": "cfcfcf",
    "Heather grey": "a9a9a9", "Stone": "d9d3c7", "Dark brown": "4a3f35", "Red": "b3242b",
    "Coral": "f27b69", "Pink": "f06ab0", "Purple": "4b3a8c", "Green": "3f7a4d",
    "Royal blue": "3557a8", "Slate blue": "4a6a84", "Light wash": "a9c1dc",
    "Mid wash": "5b7fa8", "Dark wash": "2b3a55", "Black wash": "2a2d33",
}  # fmt: skip


def color_hex(name: str) -> str | None:
    hex6 = PALETTE.get(name)
    return f"#{hex6}" if hex6 else None
