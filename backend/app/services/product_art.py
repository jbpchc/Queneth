"""Generated, art-directed product imagery (SVG).

The spec forbids real brand photos and allows royalty-free photos *or generated
placeholders*. Queneth ships generated art so the catalog looks consistent,
works offline (VM demos without internet) and never breaks a link: each
subcategory has a fashion silhouette drawn in the product's real color, with
three compositions per product (front, close-up detail, styled on a plinth).
Seller uploads (Cloudinary) replace these in Phase 8.
"""

import colorsys
import hashlib
import re
from functools import lru_cache
from xml.sax.saxutils import escape

Shape = list[tuple[str, str]]  # (role, path d)


def _circle(cx: float, cy: float, r: float) -> str:
    return f"M{cx - r} {cy} a{r} {r} 0 1 0 {2 * r} 0 a{r} {r} 0 1 0 {-2 * r} 0 Z"


def _rect(x: float, y: float, w: float, h: float, r: float = 0) -> str:
    if not r:
        return f"M{x} {y} h{w} v{h} h{-w} Z"
    return (
        f"M{x + r} {y} h{w - 2 * r} q{r} 0 {r} {r} v{h - 2 * r} q0 {r} {-r} {r} "
        f"h{-(w - 2 * r)} q{-r} 0 {-r} {-r} v{-(h - 2 * r)} q0 {-r} {r} {-r} Z"
    )


# Silhouettes in a 400 × 500 box. Roles: body (product color), shade (darker),
# line (stroke), metal (hardware), glass (translucent), light (pale detail).
SHAPES: dict[str, Shape] = {
    "dress": [
        (
            "body",
            "M160 70 L240 70 L252 120 L238 150 Q300 300 318 450 Q200 478 82 450 Q100 300 162 150 L148 120 Z",
        ),
        ("shade", "M162 150 Q200 164 238 150 L240 162 Q200 178 160 162 Z"),
        ("line", "M165 72 L172 28 M235 72 L228 28 M200 170 Q190 320 150 455"),
    ],
    "top": [
        (
            "body",
            "M150 70 Q200 96 250 70 L322 112 L298 168 L262 150 L266 362 L134 362 L138 150 L102 168 L78 112 Z",
        ),
        ("line", "M168 78 Q200 102 232 78 M200 98 L200 200"),
        ("light", _circle(200, 130, 4) + _circle(200, 160, 4) + _circle(200, 190, 4)),
    ],
    "coat": [
        (
            "body",
            "M150 58 L200 80 L250 58 L306 95 L332 442 L282 450 L270 222 L268 454 L132 454 L130 222 L118 450 L68 442 L94 95 Z",
        ),
        ("shade", "M150 58 L200 80 L180 205 L158 130 Z M250 58 L200 80 L220 205 L242 130 Z"),
        ("line", "M200 80 L200 452 M150 330 L185 330 M215 330 L250 330"),
        ("metal", _circle(212, 250, 6) + _circle(212, 290, 6)),
    ],
    "trousers": [
        ("body", "M135 60 L265 60 L286 456 L218 456 L200 176 L182 456 L114 456 Z"),
        ("shade", "M135 60 L265 60 L267 84 L133 84 Z"),
        ("line", "M160 90 L148 450 M240 90 L252 450 M200 84 L200 140"),
    ],
    "knit": [
        (
            "body",
            "M150 70 Q200 92 250 70 L312 100 L346 330 L310 342 L270 172 L268 372 L132 372 L130 172 L90 342 L54 330 L88 100 Z",
        ),
        (
            "shade",
            "M132 350 L268 350 L268 372 L132 372 Z M54 330 L90 342 L86 322 L58 312 Z M346 330 L310 342 L314 322 L342 312 Z",
        ),
        (
            "line",
            "M150 354 L150 370 M170 354 L170 370 M190 354 L190 370 M210 354 L210 370 M230 354 L230 370 M250 354 L250 370 M165 78 Q200 98 235 78",
        ),
    ],
    "blazer": [
        (
            "body",
            "M150 64 L200 86 L250 64 L310 95 L336 402 L290 410 L272 232 L270 402 L130 402 L128 232 L110 410 L64 402 L90 95 Z",
        ),
        ("shade", "M150 64 L200 86 L184 230 L160 140 Z M250 64 L200 86 L216 230 L240 140 Z"),
        ("line", "M200 86 L200 400 M140 300 L178 300 M222 300 L260 300 M232 160 L260 160"),
        ("metal", _circle(208, 260, 6)),
    ],
    "heels": [
        (
            "body",
            "M40 360 Q48 328 96 324 L208 318 Q274 312 318 254 Q344 226 360 240 Q370 300 352 354 L350 360 Z",
        ),
        ("shade", "M318 352 L348 354 L338 452 L326 452 Z"),
        ("line", "M40 360 L350 360 M96 324 Q150 300 206 318"),
    ],
    "sneakers": [
        (
            "body",
            "M40 370 Q34 320 90 300 L170 286 Q214 230 270 226 L330 236 Q366 262 362 332 L360 370 Z",
        ),
        ("shade", "M34 370 L366 370 L360 400 Q200 410 40 400 Z"),
        ("line", "M190 280 L220 300 M205 266 L238 286 M222 252 L256 272 M90 330 Q200 345 300 320"),
    ],
    "loafers": [
        ("body", "M48 366 Q54 318 122 310 L252 298 Q322 292 354 330 L356 366 Z"),
        ("shade", "M44 366 L360 366 L358 390 L46 390 Z"),
        ("line", "M140 318 Q200 298 262 304 M170 312 L232 304"),
        ("metal", _rect(186, 300, 32, 10, 4)),
    ],
    "boots": [
        (
            "body",
            "M200 88 L290 88 L298 300 Q300 330 342 340 Q374 350 370 400 L78 400 Q76 360 140 346 L190 330 Z",
        ),
        ("shade", "M74 400 L374 400 L372 424 L76 424 Z M200 88 L290 88 L291 112 L200 112 Z"),
        ("line", "M245 112 L248 320"),
    ],
    "sandals": [
        (
            "shade",
            "M50 380 Q60 360 120 358 L320 352 Q362 352 360 372 Q356 394 300 394 L80 396 Q50 396 50 380 Z",
        ),
        (
            "body",
            "M110 362 Q170 280 236 356 L222 358 Q170 300 126 362 Z M196 357 Q252 296 306 352 L292 354 Q252 316 212 357 Z",
        ),
        ("metal", _circle(236, 330, 7)),
    ],
    "tote": [
        ("body", "M90 182 L310 182 L332 442 L68 442 Z"),
        ("shade", "M90 182 L310 182 L312 210 L88 210 Z"),
        ("line", "M140 182 Q140 80 200 80 Q260 80 260 182 M128 182 Q128 64 200 64 Q272 64 272 182"),
    ],
    "shoulder": [
        (
            "body",
            "M80 220 Q80 190 110 190 L290 190 Q320 190 320 220 L320 400 Q320 422 298 422 L102 422 Q80 422 80 400 Z",
        ),
        ("shade", "M80 220 Q80 190 110 190 L290 190 Q320 190 320 220 L320 292 Q200 322 80 292 Z"),
        ("line", "M112 192 Q200 40 288 192"),
        ("metal", _circle(200, 300, 12)),
    ],
    "crossbody": [
        ("body", _rect(100, 260, 200, 150, 22)),
        ("shade", "M100 282 Q100 260 122 260 L278 260 Q300 260 300 282 L300 320 L100 320 Z"),
        ("line", "M112 262 L62 36 M288 262 L338 36"),
        ("metal", _rect(186, 312, 28, 16, 4)),
    ],
    "clutch": [
        ("body", _rect(60, 230, 280, 150, 14)),
        ("shade", "M60 244 Q60 230 74 230 L326 230 Q340 230 340 244 L200 322 Z"),
        ("metal", _circle(200, 318, 9)),
    ],
    "backpack": [
        (
            "body",
            "M110 122 Q110 90 140 90 L260 90 Q290 90 290 122 L300 430 Q300 452 278 452 L122 452 Q100 452 100 430 Z",
        ),
        ("shade", _rect(128, 300, 144, 122, 12)),
        ("line", "M170 90 Q200 52 230 90 M128 320 L272 320"),
        ("metal", _rect(190, 330, 20, 12, 3)),
    ],
    "necklace": [
        ("line", "M88 80 Q200 360 312 80"),
        ("metal", _circle(200, 334, 34)),
        ("body", _circle(200, 334, 24)),
        ("light", _circle(192, 326, 7)),
    ],
    "watch": [
        ("shade", _rect(165, 30, 70, 440, 18)),
        ("metal", _circle(200, 250, 88)),
        ("light", _circle(200, 250, 72)),
        (
            "line",
            "M200 250 L200 196 M200 250 L236 268 M200 186 L200 194 M264 250 L256 250 M200 314 L200 306 M136 250 L144 250",
        ),
        ("body", _circle(200, 250, 6)),
    ],
    "sunglasses": [
        (
            "glass",
            "M58 232 Q58 200 100 200 L172 200 Q192 200 192 232 Q190 302 124 302 Q58 302 58 232 Z M342 232 Q342 200 300 200 L228 200 Q208 200 208 232 Q210 302 276 302 Q342 302 342 232 Z",
        ),
        ("line", "M192 222 Q200 210 208 222 M58 214 L18 196 M342 214 L382 196"),
        ("light", "M84 222 L120 210 L116 222 Z M244 222 L280 210 L276 222 Z"),
    ],
    "belt": [
        ("body", "M24 236 L330 226 L332 276 L26 286 Z"),
        ("metal", "M300 214 L372 212 L374 292 L302 294 Z M314 228 L358 226 L360 278 L316 280 Z"),
        ("line", "M70 260 L290 252"),
    ],
    "scarf": [
        (
            "body",
            "M110 60 Q200 102 290 60 L302 122 Q252 262 302 442 Q200 472 118 442 Q160 282 98 122 Z",
        ),
        (
            "line",
            "M130 120 Q200 150 270 120 M150 200 Q200 225 250 200 M140 300 Q200 325 262 300 M138 400 Q200 425 270 400",
        ),
        ("shade", "M118 442 Q200 472 302 442 L300 460 Q200 488 120 460 Z"),
    ],
    "hat": [
        ("body", "M120 252 Q120 148 200 144 Q280 148 280 252 Z"),
        ("body", "M40 262 Q40 226 200 224 Q360 226 360 262 Q360 296 200 298 Q40 296 40 262 Z"),
        ("shade", "M120 226 Q200 236 280 226 L280 252 Q200 262 120 252 Z"),
    ],
    "perfume-0": [
        ("glass", _rect(120, 180, 160, 272, 22)),
        ("metal", _rect(180, 146, 40, 36, 4)),
        ("shade", _rect(160, 76, 80, 72, 10)),
        ("light", _rect(150, 292, 100, 62, 4)),
    ],
    "perfume-1": [
        ("glass", _circle(200, 330, 128)),
        ("metal", _rect(182, 172, 36, 34, 4)),
        ("shade", _circle(200, 140, 40)),
        ("light", _rect(160, 312, 80, 44, 4)),
    ],
    "perfume-2": [
        ("glass", "M150 180 L250 180 L300 230 L300 400 L250 450 L150 450 L100 400 L100 230 Z"),
        ("metal", _rect(178, 144, 44, 38, 4)),
        ("shade", "M164 60 L236 60 L250 146 L150 146 Z"),
        ("light", _rect(156, 296, 88, 58, 4)),
    ],
    "giftbox": [
        ("body", _rect(70, 200, 260, 230, 10)),
        ("shade", _rect(58, 168, 284, 48, 8)),
        (
            "metal",
            "M188 168 L212 168 L212 430 L188 430 Z M120 120 Q170 120 200 170 Q160 180 120 160 Z M280 120 Q230 120 200 170 Q240 180 280 160 Z",
        ),
    ],
}

#: Visual center and hero scale per silhouette, so every product fills the frame.
FRAMING: dict[str, tuple[float, float, float]] = {
    "dress": (200, 262, 1.45), "top": (200, 216, 1.6), "coat": (200, 256, 1.4),
    "trousers": (200, 258, 1.4), "knit": (200, 222, 1.5), "blazer": (200, 236, 1.5),
    "heels": (200, 342, 1.65), "sneakers": (200, 318, 1.65), "loafers": (202, 344, 1.75),
    "boots": (224, 256, 1.45), "sandals": (205, 372, 1.8), "tote": (200, 262, 1.45),
    "shoulder": (200, 300, 1.55), "crossbody": (200, 236, 1.45), "clutch": (200, 305, 1.7),
    "backpack": (200, 272, 1.4), "necklace": (200, 214, 1.5), "watch": (200, 250, 1.45),
    "sunglasses": (200, 250, 1.65), "belt": (200, 255, 1.7), "scarf": (200, 262, 1.45),
    "hat": (200, 222, 1.6), "perfume-0": (200, 266, 1.45), "perfume-1": (200, 300, 1.45),
    "perfume-2": (200, 256, 1.45), "giftbox": (200, 292, 1.5),
}  # fmt: skip

SUBCATEGORY_SHAPE = {
    "dresses": "dress", "tops": "top", "outerwear": "coat", "trousers": "trousers",
    "knitwear": "knit", "suiting": "blazer", "heels": "heels", "sneakers": "sneakers",
    "loafers": "loafers", "boots": "boots", "sandals": "sandals", "totes": "tote",
    "shoulder": "shoulder", "crossbody": "crossbody", "clutches": "clutch",
    "backpacks": "backpack", "jewelry": "necklace", "watches": "watch",
    "sunglasses": "sunglasses", "belts": "belt", "scarves": "scarf", "hats": "hat",
    "women": "perfume", "men": "perfume", "unisex": "perfume", "niche": "perfume",
    "gift-sets": "giftbox",
}  # fmt: skip

HEX = re.compile(r"^[0-9a-fA-F]{6}$")


def shape_for(subcategory_slug: str, seed: str) -> str:
    shape = SUBCATEGORY_SHAPE.get(subcategory_slug, "tote")
    if shape == "perfume":
        return f"perfume-{int(hashlib.md5(seed.encode()).hexdigest(), 16) % 3}"  # noqa: S324
    return shape


def _rgb(hex6: str) -> tuple[float, float, float]:
    return tuple(int(hex6[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb)


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(x + (y - x) * t for x, y in zip(ra, rb, strict=True)))  # type: ignore[arg-type]


def _shift(hex6: str, *, light: float = 0, sat: float = 0, hue: float = 0) -> str:
    h, l_, s = colorsys.rgb_to_hls(*_rgb(hex6))
    return _hex(
        colorsys.hls_to_rgb((h + hue) % 1, max(0, min(1, l_ + light)), max(0, min(1, s + sat)))
    )


@lru_cache(maxsize=2048)
def render(shape: str, n: int, color: str, monogram: str = "") -> str:
    """SVG 800×1000 (4:5). n=1 front, n=2 close-up detail, n=3 styled plinth."""
    color = color.lower()
    parts = SHAPES[shape]
    porcelain = "faf7f2"
    lum = sum(_rgb(color)) / 3
    if n == 2:
        bg_a, bg_b = _shift(color, light=-0.28), _shift(color, light=-0.12)
    elif n == 3:
        bg_a, bg_b = _shift(color, light=0.32, hue=0.08, sat=-0.2), _mix(porcelain, color, 0.12)
    else:
        bg_a, bg_b = _mix(porcelain, color, 0.06), _mix(porcelain, color, 0.2)
    body = "#" + color
    shade = _shift(color, light=-0.14 if lum > 0.2 else 0.1)
    line = _shift(color, light=-0.3 if lum > 0.25 else 0.28)
    light = _mix("ffffff", color, 0.12)
    fills = {
        "body": f'fill="{body}"',
        "shade": f'fill="{shade}"',
        "line": f'fill="none" stroke="{line}" stroke-width="5" stroke-linecap="round"',
        "metal": 'fill="url(#metal)"',
        "glass": f'fill="{body}" fill-opacity="0.62" stroke="{shade}" stroke-width="4"',
        "light": f'fill="{light}" fill-opacity="0.9"',
    }
    paths = "".join(f'<path d="{d}" {fills[role]}/>' for role, d in parts)
    cx, cy, scale = FRAMING.get(shape, (200, 250, 1.45))
    if n == 2:  # close-up crop into the detail
        k = scale * 1.85
        transform = f"translate({400 - cx * k:.1f} {500 - (cy - 30) * k:.1f}) scale({k:.2f})"
    elif n == 3:  # smaller, standing on a plinth
        k = scale * 0.72
        transform = f"translate({400 - cx * k:.1f} {520 - cy * k:.1f}) scale({k:.2f})"
    else:  # hero: centered, filling the frame
        transform = f"translate({400 - cx * scale:.1f} {480 - cy * scale:.1f}) scale({scale:.2f})"
    plinth = ""
    if n == 3:
        plinth = (
            f'<ellipse cx="400" cy="745" rx="250" ry="46" fill="{_shift(color, light=0.22, sat=-0.25)}"/>'
            f'<rect x="150" y="745" width="500" height="255" fill="{_shift(color, light=0.16, sat=-0.25)}"/>'
        )
        if monogram:
            plinth += (
                f'<text x="400" y="900" text-anchor="middle" font-family="Georgia, serif" '
                f'font-size="64" letter-spacing="18" fill="{_shift(color, light=-0.05, sat=-0.3)}" '
                f'fill-opacity="0.55">{escape(monogram)}</text>'
            )
    shadow = (
        ""
        if n != 1
        else '<ellipse cx="400" cy="870" rx="230" ry="24" fill="#000" fill-opacity="0.06"/>'
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 1000" width="800" height="1000">'
        "<defs>"
        f'<linearGradient id="bg" x1="0" y1="0" x2="0.3" y2="1"><stop offset="0" stop-color="{bg_a}"/>'
        f'<stop offset="1" stop-color="{bg_b}"/></linearGradient>'
        '<linearGradient id="metal" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e9d39a"/>'
        '<stop offset="0.5" stop-color="#c9a44c"/><stop offset="1" stop-color="#8a6a28"/></linearGradient>'
        '<radialGradient id="glow" cx="0.5" cy="0.35" r="0.6"><stop offset="0" stop-color="#fff" stop-opacity="0.45"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        "</defs>"
        '<rect width="800" height="1000" fill="url(#bg)"/><rect width="800" height="1000" fill="url(#glow)"/>'
        f'{plinth}{shadow}<g transform="{transform}">{paths}</g></svg>'
    )


@lru_cache(maxsize=256)
def render_logo(initials: str, color: str) -> str:
    fg = (
        _shift(color, light=0.42, sat=-0.2)
        if sum(_rgb(color)) / 3 < 0.5
        else _shift(color, light=-0.45)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="240" height="240">'
        f'<rect width="240" height="240" rx="120" fill="#{color}"/>'
        f'<circle cx="120" cy="120" r="104" fill="none" stroke="{fg}" stroke-opacity="0.35" stroke-width="2"/>'
        f'<text x="120" y="142" text-anchor="middle" font-family="Georgia, serif" font-size="68" '
        f'letter-spacing="4" fill="{fg}">{escape(initials)}</text></svg>'
    )


@lru_cache(maxsize=256)
def render_banner(color: str, shape: str) -> str:
    a, b = _shift(color, light=0.3, sat=-0.25), _shift(color, light=0.12, sat=-0.15)
    shapes = "".join(
        f'<g transform="translate({x} {y}) scale({s}) rotate({r} 200 250)" opacity="{o}">'
        + "".join(
            f'<path d="{d}" fill="{_shift(color, light=dl)}"/>'
            for _, d in SHAPES[shape]
            if _ != "line"
        )
        + "</g>"
        for x, y, s, r, o, dl in (
            (980, -40, 0.9, -8, 0.55, -0.05),
            (1280, 120, 0.6, 10, 0.35, 0.05),
            (720, 200, 0.45, 4, 0.25, 0.1),
        )
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 600" width="1600" height="600">'
        f'<defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/>'
        f'<stop offset="1" stop-color="{b}"/></linearGradient></defs>'
        f'<rect width="1600" height="600" fill="url(#b)"/>{shapes}</svg>'
    )
