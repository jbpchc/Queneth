"""Small text helpers shared by services and the seed."""

import re
import unicodedata


def slugify(text: str) -> str:
    """'Maison Verdé Silk Slip' -> 'maison-verde-silk-slip'."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
