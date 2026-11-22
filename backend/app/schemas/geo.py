from typing import Annotated, Literal

from fastapi import Path, Query

from app.schemas.common import ApiModel

# PSGC codes are 9 digits (e.g. Camarines Sur = 051700000).
PsgcCode = Annotated[str, Path(pattern=r"^\d{9}$", examples=["051700000"])]
PsgcCodeQuery = Annotated[str | None, Query(pattern=r"^\d{9}$")]


class GeoArea(ApiModel):
    code: str
    name: str


class GeoList(ApiModel):
    items: list[GeoArea]
    #: Where this answer came from: the live PSGC API, the 30-day DB cache, or
    #: the bundled offline snapshot (mock mode or fallback).
    source: Literal["live", "cache", "snapshot"]


class PlaceNames(ApiModel):
    barangay: str | None
    city: str
    province: str | None
    region: str | None
