"""Aggregates every v1 module router. Each later phase adds one line here."""

from fastapi import APIRouter

from app.api.v1.routers import (
    addresses,
    admin,
    admin_room,
    admin_wallet,
    art,
    auth,
    catalog,
    geo,
    health,
    me,
    media,
    notifications,
    orders,
    promotions,
    reviews,
    seller,
    shop,
    studio,
    wallet,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(geo.router)
api_router.include_router(art.router)
api_router.include_router(catalog.router)
api_router.include_router(shop.wishlist_router)
api_router.include_router(shop.cart_router)
api_router.include_router(addresses.router)
api_router.include_router(orders.router)
api_router.include_router(reviews.router)
api_router.include_router(seller.router)
api_router.include_router(studio.router)
api_router.include_router(studio.application_router)
api_router.include_router(media.router)
api_router.include_router(notifications.router)
api_router.include_router(wallet.router)
api_router.include_router(admin.router)
api_router.include_router(admin_wallet.router)
api_router.include_router(admin_room.router)
api_router.include_router(admin_room.reports_router)
api_router.include_router(promotions.public_router)
api_router.include_router(promotions.seller_router)
api_router.include_router(promotions.admin_router)
