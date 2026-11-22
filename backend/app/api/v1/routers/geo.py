"""Public PSGC lists for cascading address dropdowns (proxied, cached, with an
offline fallback). Browsers cache responses for a day; data changes rarely."""

from fastapi import APIRouter, Depends, Response

from app.api.deps import AppSettings, DbSession
from app.schemas.geo import GeoArea, GeoList, PlaceNames, PsgcCode, PsgcCodeQuery
from app.services.geo_service import GeoService

router = APIRouter(prefix="/geo", tags=["geo"])


def get_geo_service(session: DbSession, settings: AppSettings) -> GeoService:
    return GeoService(session, settings)


def _out(response: Response, result: tuple[list, str]) -> GeoList:
    items, source = result
    response.headers["Cache-Control"] = "public, max-age=86400"
    return GeoList(items=[GeoArea(code=i.code, name=i.name) for i in items], source=source)  # type: ignore[arg-type]


@router.get("/regions", response_model=GeoList, summary="All 17 regions")
async def regions(response: Response, geo: GeoService = Depends(get_geo_service)) -> GeoList:
    return _out(response, await geo.regions())


@router.get(
    "/regions/{region_code}/provinces",
    response_model=GeoList,
    summary="Provinces in a region (empty for NCR)",
)
async def provinces(
    region_code: PsgcCode, response: Response, geo: GeoService = Depends(get_geo_service)
) -> GeoList:
    return _out(response, await geo.provinces(region_code))


@router.get(
    "/regions/{region_code}/cities",
    response_model=GeoList,
    summary="Cities and municipalities in a province, or province-less cities of a region",
)
async def cities(
    region_code: PsgcCode,
    response: Response,
    province: PsgcCodeQuery = None,
    geo: GeoService = Depends(get_geo_service),
) -> GeoList:
    return _out(response, await geo.cities(region_code=region_code, province_code=province))


@router.get(
    "/cities/{city_code}/barangays",
    response_model=GeoList,
    summary="Barangays in a city or municipality",
)
async def barangays(
    city_code: PsgcCode, response: Response, geo: GeoService = Depends(get_geo_service)
) -> GeoList:
    return _out(response, await geo.barangays(city_code))


@router.get(
    "/barangays/{barangay_code}",
    response_model=PlaceNames,
    summary="Resolve a barangay code to its full place names",
)
async def resolve(
    barangay_code: PsgcCode, geo: GeoService = Depends(get_geo_service)
) -> PlaceNames:
    return PlaceNames(**geo.resolve_barangay(barangay_code))
