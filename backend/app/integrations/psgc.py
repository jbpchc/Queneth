"""PSGC (Philippine Standard Geographic Code) adapter.

Live source: psgc.gitlab.io/api (static JSON mirror of the PSA's PSGC, no key).
Fallback and mock source: `data/psgc_snapshot.json.gz`, bundled with the app
(17 regions, 81 provinces, 1,634 cities/municipalities, 42,046 barangays).

Shape quirks handled here so callers don't have to:
- NCR has no provinces; its cities hang directly off the region.
- A few independent cities (e.g. Isabela City, Cotabato City) sit in regions
  that do have provinces, but belong to none of them.
"""

import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from app.integrations.base import HttpAdapter, IntegrationName

SNAPSHOT_PATH = Path(__file__).parent / "data" / "psgc_snapshot.json.gz"


class PsgcArea(BaseModel):
    code: str
    name: str


class PsgcCity(PsgcArea):
    province_code: str | None
    region_code: str
    is_city: bool


class _LiveCity(BaseModel):
    code: str
    name: str
    provinceCode: str | bool  # the API uses `false` for "none"
    regionCode: str
    isCity: bool


_areas = TypeAdapter(list[PsgcArea])
_live_cities = TypeAdapter(list[_LiveCity])


def _sorted[T: PsgcArea](items: list[T]) -> list[T]:
    return sorted(items, key=lambda a: a.name.casefold())


class PsgcAdapter(HttpAdapter):
    """Live HTTP calls only. Caching and fallback live in geo_service."""

    name = IntegrationName.PSGC

    async def _get(self, path: str) -> Any:
        async def fetch() -> Any:
            async with self.client(base_url=self.settings.psgc_base_url) as client:
                res = await client.get(path)
                res.raise_for_status()
                return res.json()

        return await self.call(f"GET {path}", fetch)

    async def regions(self) -> list[PsgcArea]:
        return _sorted(_areas.validate_python(await self._get("/regions.json")))

    async def provinces(self, region_code: str) -> list[PsgcArea]:
        return _sorted(
            _areas.validate_python(await self._get(f"/regions/{region_code}/provinces.json"))
        )

    async def region_cities(self, region_code: str) -> list[PsgcCity]:
        raw = _live_cities.validate_python(
            await self._get(f"/regions/{region_code}/cities-municipalities.json")
        )
        return _sorted([_to_city(c) for c in raw])

    async def barangays(self, city_code: str) -> list[PsgcArea]:
        return _sorted(
            _areas.validate_python(
                await self._get(f"/cities-municipalities/{city_code}/barangays.json")
            )
        )

    async def ping(self) -> None:
        await self._get("/regions.json")


def _to_city(c: _LiveCity) -> PsgcCity:
    return PsgcCity(
        code=c.code,
        name=c.name,
        province_code=c.provinceCode if isinstance(c.provinceCode, str) else None,
        region_code=c.regionCode,
        is_city=c.isCity,
    )


class PsgcSnapshot:
    """Offline copy of the PSGC lists, loaded once per process (~320 KB gzipped)."""

    def __init__(self, data: dict[str, Any]):
        self.generated: str = data.get("generated", "")
        self._regions = [PsgcArea(code=c, name=n) for c, n, _ in data["regions"]]
        self._provinces: dict[str, list[PsgcArea]] = {}
        for code, name, region in data["provinces"]:
            self._provinces.setdefault(region, []).append(PsgcArea(code=code, name=name))
        self._cities: dict[str, list[PsgcCity]] = {}
        for code, name, province, region, is_city in data["cities"]:
            city = PsgcCity(
                code=code, name=name, province_code=province, region_code=region, is_city=is_city
            )
            self._cities.setdefault(region, []).append(city)
        self._barangays: dict[str, list[PsgcArea]] = {}
        self._barangay_parent: dict[str, str] = {}
        for code, name, city in data["barangays"]:
            self._barangays.setdefault(city, []).append(PsgcArea(code=code, name=name))
            self._barangay_parent[code] = city
        self._names = {a.code: a.name for a in self._regions}
        self._names.update({p.code: p.name for ps in self._provinces.values() for p in ps})
        self._names.update({c.code: c.name for cs in self._cities.values() for c in cs})
        self._city_by_code = {c.code: c for cs in self._cities.values() for c in cs}

    def regions(self) -> list[PsgcArea]:
        return _sorted(self._regions)

    def provinces(self, region_code: str) -> list[PsgcArea]:
        return _sorted(self._provinces.get(region_code, []))

    def region_cities(self, region_code: str) -> list[PsgcCity]:
        return _sorted(self._cities.get(region_code, []))

    def barangays(self, city_code: str) -> list[PsgcArea]:
        return _sorted(self._barangays.get(city_code, []))

    def name_of(self, code: str) -> str | None:
        return self._names.get(code)

    def city(self, code: str) -> PsgcCity | None:
        return self._city_by_code.get(code)

    def barangay_city(self, barangay_code: str) -> str | None:
        return self._barangay_parent.get(barangay_code)

    def barangay_name(self, barangay_code: str) -> str | None:
        city = self._barangay_parent.get(barangay_code)
        if city is None:
            return None
        return next((b.name for b in self._barangays[city] if b.code == barangay_code), None)


@lru_cache(maxsize=1)
def load_snapshot() -> PsgcSnapshot:
    with gzip.open(SNAPSHOT_PATH, "rt", encoding="utf-8") as f:
        return PsgcSnapshot(json.load(f))
