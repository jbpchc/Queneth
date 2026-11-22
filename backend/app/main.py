"""Queneth API entry point: `uvicorn app.main:app`."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.csrf import csrf_middleware
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import limiter, rate_limit_handler
from app.core.scheduler import build_scheduler
from app.db.session import SessionLocal, engine
from app.schemas.common import ERROR_RESPONSES

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = build_scheduler(app.state.session_factory, settings)
        scheduler.start()
    log.info("api_startup", integrations_mode=settings.integrations_mode)
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await engine.dispose()
    log.info("api_shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.is_production)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "REST API for Queneth, a multi-vendor fashion marketplace. "
            'All errors use the envelope `{"error": {"code", "message", "details"}}`. '
            "QueWallet credits are simulated for academic purposes and have no cash value."
        ),
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware runs outermost-last-registered. Order, outside → in:
    # CORS (so even CSRF/limit rejections carry CORS headers) → request id → CSRF.
    app.middleware("http")(csrf_middleware)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    register_error_handlers(app)
    app.state.settings = settings
    # Background work (email delivery, scheduler) opens sessions from here;
    # tests swap in the test database's factory.
    app.state.session_factory = SessionLocal
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.include_router(api_router, prefix=settings.api_v1_prefix, responses=ERROR_RESPONSES)

    # Local-disk uploads (Cloudinary mock mode / fallback). Only the generated
    # public ids are ever written here, so nothing user-named is served.
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        f"{settings.api_v1_prefix}/media/files",
        StaticFiles(directory=settings.upload_dir),
        name="media-files",
    )
    return app


app = create_app()
