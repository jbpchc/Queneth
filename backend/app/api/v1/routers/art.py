"""Generated catalog imagery (see services/product_art.py). Deterministic and
immutable, so responses are cached for a year by browsers and CDNs."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Response

from app.core.errors import NotFound
from app.services.product_art import SHAPES, render, render_banner, render_logo

router = APIRouter(prefix="/catalog/art", tags=["catalog"])

Color = Annotated[str, Query(pattern=r"^[0-9a-fA-F]{6}$", description="Hex color without #")]
IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


def _svg(body: str) -> Response:
    return Response(content=body, media_type="image/svg+xml", headers=IMMUTABLE)


@router.get("/p/{shape}/{n}.svg", summary="Product image", response_class=Response)
async def product_art(
    shape: Annotated[str, Path(max_length=24)],
    n: Annotated[int, Path(ge=1, le=3)],
    c: Color,
    m: Annotated[str, Query(max_length=3, pattern=r"^[A-Za-z]*$")] = "",
) -> Response:
    if shape not in SHAPES:
        raise NotFound("Unknown artwork.")
    return _svg(render(shape, n, c, m.upper()))


@router.get("/logo.svg", summary="Boutique monogram logo", response_class=Response)
async def logo(
    c: Color, t: Annotated[str, Query(max_length=3, pattern=r"^[A-Za-z&]+$")]
) -> Response:
    return _svg(render_logo(t.upper(), c.lower()))


@router.get("/banner/{shape}.svg", summary="Boutique banner", response_class=Response)
async def banner(shape: Annotated[str, Path(max_length=24)], c: Color) -> Response:
    if shape not in SHAPES:
        raise NotFound("Unknown artwork.")
    return _svg(render_banner(c.lower(), shape))
