"""Public catalog. Guests and shoppers alike; signed-in users also get their
follow / notify state."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import AppSettings, CurrentUser, DbSession, OptionalUser
from app.schemas.catalog import (
    BoutiqueCard,
    BoutiqueDetail,
    CategoryOut,
    CollectionOut,
    DropOut,
    FollowState,
    HomeOut,
    ProductDetail,
    ProductListing,
    ReviewOut,
    SortKey,
    SubscriptionState,
    Suggestion,
)
from app.schemas.common import CursorPage
from app.services import shop_service
from app.services.catalog_service import CatalogService, ListingParams

router = APIRouter(prefix="/catalog", tags=["catalog"])

Many = Annotated[list[str], Query()]


def get_catalog(session: DbSession, settings: AppSettings) -> CatalogService:
    return CatalogService(session, settings)


Catalog = Annotated[CatalogService, Depends(get_catalog)]


def _cache(response: Response, seconds: int = 60) -> None:
    response.headers["Cache-Control"] = f"public, max-age={seconds}, stale-while-revalidate=300"


@router.get("/home", response_model=HomeOut, summary="Everything the home page needs, in one call")
async def home(catalog: Catalog, user: OptionalUser) -> HomeOut:
    return await catalog.home(user)


@router.get(
    "/categories",
    response_model=list[CategoryOut],
    summary="Categories with subcategories and counts",
)
async def categories(catalog: Catalog, response: Response) -> list[CategoryOut]:
    _cache(response, 300)
    return await catalog.categories()


@router.get("/categories/{slug}", response_model=CategoryOut)
async def category(slug: str, catalog: Catalog) -> CategoryOut:
    return await catalog.category(slug)


@router.get(
    "/products",
    response_model=ProductListing,
    summary="Faceted product listing and full-text search (typo tolerant)",
)
async def products(
    catalog: Catalog,
    response: Response,
    q: Annotated[str | None, Query(max_length=80)] = None,
    category: str | None = None,
    subcategory: str | None = None,
    brand: Many = [],  # noqa: B006
    boutique: Many = [],  # noqa: B006
    size: Many = [],  # noqa: B006
    color: Many = [],  # noqa: B006
    condition: Many = [],  # noqa: B006
    facet: Annotated[
        list[str],
        Query(description="Category facet as key:value, e.g. notes:bergamot or family:Woody"),
    ] = [],  # noqa: B006
    price_min: Annotated[int | None, Query(ge=0)] = None,
    price_max: Annotated[int | None, Query(ge=0)] = None,
    tag: str | None = None,
    in_stock: bool = False,
    sort: SortKey = "curated",
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=96)] = None,
) -> ProductListing:
    facets: dict[str, list[str]] = {}
    for f in facet:
        key, _, value = f.partition(":")
        if key and value:
            facets.setdefault(key.strip(), []).append(value.strip())
    listing, corrected = await catalog.listing(
        ListingParams(
            q=q.strip() if q else None,
            category=category,
            subcategory=subcategory,
            brands=brand,
            boutiques=boutique,
            sizes=size,
            colors=color,
            conditions=condition,
            price_min=price_min,
            price_max=price_max,
            facets=facets,
            tag=tag,
            in_stock=in_stock,
            sort=sort,
            cursor=cursor,
            limit=limit,
        )
    )
    if corrected:
        response.headers["X-Search-Corrected"] = corrected
    return listing


@router.get(
    "/suggest", response_model=Suggestion, summary="Autosuggest: products, brands, boutiques"
)
async def suggest(
    catalog: Catalog, q: Annotated[str, Query(min_length=2, max_length=60)]
) -> Suggestion:
    return await catalog.suggest(q)


@router.get("/products/{slug}", response_model=ProductDetail, summary="Product page")
async def product(slug: str, catalog: Catalog, user: OptionalUser) -> ProductDetail:
    return await catalog.product_detail(slug, user)


@router.get(
    "/products/{slug}/reviews",
    response_model=CursorPage[ReviewOut],
    summary="Reviews, newest first",
)
async def reviews(
    slug: str,
    catalog: Catalog,
    cursor: str | None = None,
    limit: Annotated[int | None, Query(ge=1, le=48)] = None,
    photos: bool = False,
) -> CursorPage[ReviewOut]:
    items, nxt = await catalog.reviews(slug, cursor=cursor, limit=limit, with_photos=photos)
    return CursorPage[ReviewOut](items=items, next_cursor=nxt, has_more=nxt is not None)


@router.get("/boutiques", response_model=list[BoutiqueCard], summary="All approved boutiques")
async def boutiques(catalog: Catalog, user: OptionalUser) -> list[BoutiqueCard]:
    return await catalog.boutiques(user)


@router.get("/boutiques/{slug}", response_model=BoutiqueDetail, summary="Boutique storefront")
async def boutique(slug: str, catalog: Catalog, user: OptionalUser) -> BoutiqueDetail:
    return await catalog.boutique(slug, user)


@router.put("/boutiques/{slug}/follow", response_model=FollowState, summary="Follow a boutique")
async def follow(slug: str, session: DbSession, user: CurrentUser) -> FollowState:
    on, count = await shop_service.follow(session, user, slug, True)
    return FollowState(is_following=on, follower_count=count)


@router.delete(
    "/boutiques/{slug}/follow", response_model=FollowState, summary="Unfollow a boutique"
)
async def unfollow(slug: str, session: DbSession, user: CurrentUser) -> FollowState:
    on, count = await shop_service.follow(session, user, slug, False)
    return FollowState(is_following=on, follower_count=count)


@router.get("/collections", response_model=list[CollectionOut], summary="Editorial collections")
async def collections(catalog: Catalog) -> list[CollectionOut]:
    return await catalog.collections()


@router.get("/collections/{slug}", response_model=CollectionOut, summary="One editorial collection")
async def collection(slug: str, catalog: Catalog) -> CollectionOut:
    return await catalog.collection(slug)


@router.get("/drops", response_model=list[DropOut], summary="Live and upcoming drops")
async def drops(catalog: Catalog, user: OptionalUser) -> list[DropOut]:
    return await catalog.drops(user)


@router.put(
    "/drops/{slug}/notify", response_model=SubscriptionState, summary="Notify me when it goes live"
)
async def notify(slug: str, session: DbSession, user: CurrentUser) -> SubscriptionState:
    return SubscriptionState(
        is_subscribed=await shop_service.notify_drop(session, user, slug, True)
    )


@router.delete(
    "/drops/{slug}/notify", response_model=SubscriptionState, summary="Stop notifications"
)
async def unnotify(slug: str, session: DbSession, user: CurrentUser) -> SubscriptionState:
    return SubscriptionState(
        is_subscribed=await shop_service.notify_drop(session, user, slug, False)
    )
