"""Region → province → city/municipality → barangay lists for address forms.

Order of sources, per request:
1. mock mode → bundled snapshot
2. fresh DB cache (≤ PSGC_CACHE_DAYS old) → cache
3. live PSGC API → cache it, return it
4. live failed → stale cache if any, else bundled snapshot

So the address picker keeps working when the PSGC API is down (as it was for
psgc-api.wareneutron.com while this was built).
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFound
from app.core.security import as_aware, utcnow
from app.integrations.base import IntegrationError, IntegrationName, registry
from app.integrations.psgc import PsgcAdapter, PsgcArea, PsgcCity, load_snapshot
from app.models.integration import GeoCache

Source = Literal["live", "cache", "snapshot"]
INDEPENDENT_LABEL = "Independent cities"


class GeoService:
    def __init__(
        self, session: AsyncSession, settings: Settings, adapter: PsgcAdapter | None = None
    ):
        self.session = session
        self.settings = settings
        self.adapter = adapter or PsgcAdapter(settings)
        self.snapshot = load_snapshot()

    async def _cached(
        self,
        key: str,
        live: Callable[[], Awaitable[list[PsgcArea]]],
        offline: Callable[[], list[PsgcArea]],
    ) -> tuple[list[PsgcArea], Source]:
        if self.adapter.mock:
            return offline(), "snapshot"
        row = await self.session.get(GeoCache, key)
        max_age = timedelta(days=self.settings.psgc_cache_days)
        if row and utcnow() - as_aware(row.fetched_at) < max_age:
            return [PsgcArea.model_validate(i) for i in row.payload], "cache"
        try:
            items = await live()
        except IntegrationError:
            registry.fallback(IntegrationName.PSGC)
            if row:
                return [PsgcArea.model_validate(i) for i in row.payload], "cache"
            return offline(), "snapshot"
        payload = [{"code": i.code, "name": i.name} for i in items]
        if row:
            row.payload, row.fetched_at = payload, utcnow()
        else:
            self.session.add(GeoCache(key=key, payload=payload, fetched_at=utcnow()))
        await self.session.commit()
        return items, "live"

    async def regions(self) -> tuple[list[PsgcArea], Source]:
        return await self._cached("regions", self.adapter.regions, self.snapshot.regions)

    async def _region_cities(self, region_code: str) -> tuple[list[PsgcCity], Source]:
        """Cities with their province code (needed to spot independent cities)."""
        if self.adapter.mock:
            return self.snapshot.region_cities(region_code), "snapshot"
        try:
            return await self.adapter.region_cities(region_code), "live"
        except IntegrationError:
            registry.fallback(IntegrationName.PSGC)
            return self.snapshot.region_cities(region_code), "snapshot"

    async def provinces(self, region_code: str) -> tuple[list[PsgcArea], Source]:
        """Provinces of a region. If the region also has cities outside every
        province, a virtual "Independent cities" entry (code = region code) is
        appended so those cities stay reachable. NCR returns [] (no provinces)."""

        async def live() -> list[PsgcArea]:
            provinces = await self.adapter.provinces(region_code)
            cities = await self.adapter.region_cities(region_code)
            return _with_independent(region_code, provinces, cities)

        def offline() -> list[PsgcArea]:
            return _with_independent(
                region_code,
                self.snapshot.provinces(region_code),
                self.snapshot.region_cities(region_code),
            )

        return await self._cached(f"provinces:{region_code}", live, offline)

    async def cities(
        self, *, region_code: str, province_code: str | None
    ) -> tuple[list[PsgcArea], Source]:
        """Cities/municipalities of a province; or, with no province (NCR) or the
        virtual independent-cities code, the region's province-less cities."""
        key = f"cities:{region_code}:{province_code or '-'}"

        async def live() -> list[PsgcArea]:
            return _filter_cities(
                await self.adapter.region_cities(region_code), region_code, province_code
            )

        def offline() -> list[PsgcArea]:
            return _filter_cities(
                self.snapshot.region_cities(region_code), region_code, province_code
            )

        return await self._cached(key, live, offline)

    async def barangays(self, city_code: str) -> tuple[list[PsgcArea], Source]:
        return await self._cached(
            f"barangays:{city_code}",
            lambda: self.adapter.barangays(city_code),
            lambda: self.snapshot.barangays(city_code),
        )

    def resolve_barangay(self, barangay_code: str) -> dict[str, str | None]:
        """Full place names for a barangay code (offline; used to validate and
        snapshot addresses server-side in Phase 6)."""
        city_code = self.snapshot.barangay_city(barangay_code)
        city = self.snapshot.city(city_code) if city_code else None
        if city is None:
            raise NotFound("We couldn't find that barangay.", code="unknown_barangay")
        return {
            "barangay": self.snapshot.barangay_name(barangay_code),
            "city": city.name,
            "province": self.snapshot.name_of(city.province_code) if city.province_code else None,
            "region": self.snapshot.name_of(city.region_code),
        }


def _with_independent(
    region_code: str, provinces: list[PsgcArea], cities: list[PsgcCity]
) -> list[PsgcArea]:
    if provinces and any(c.province_code is None for c in cities):
        return [*provinces, PsgcArea(code=region_code, name=INDEPENDENT_LABEL)]
    return provinces


def _filter_cities(
    cities: list[PsgcCity], region_code: str, province_code: str | None
) -> list[PsgcArea]:
    if province_code is None or province_code == region_code:
        picked = [c for c in cities if c.province_code is None]
    else:
        picked = [c for c in cities if c.province_code == province_code]
    return [PsgcArea(code=c.code, name=c.name) for c in picked]
