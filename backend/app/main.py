"""Queneth API entry point: `uvicorn app.main:app`."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.api.v1.routers.health import router as health_router
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


SWAGGER_CSRF = """requestInterceptor: (req) => {
        const m = document.cookie.match(/(?:^|; )qn_csrf=([^;]+)/);
        if (m) req.headers["X-CSRF-Token"] = decodeURIComponent(m[1]);
        return req;
    },"""


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
        docs_url=None,  # served below, with the CSRF header wired in
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

    @app.api_route("/docs", methods=["GET", "HEAD"], include_in_schema=False)
    async def swagger_ui() -> HTMLResponse:
        """Swagger UI whose "Try it out" works with the signed-in session: it
        echoes the readable CSRF cookie in X-CSRF-Token, like the storefront."""
        page = get_swagger_ui_html(
            openapi_url=f"{settings.api_v1_prefix}/openapi.json", title=settings.app_name
        )
        html = page.body.decode().replace("presets: [", SWAGGER_CSRF + "\n    presets: [", 1)
        return HTMLResponse(html)

    # Unversioned alias for health checks and quick `curl` tests.
    app.include_router(health_router, prefix="/api", include_in_schema=False)

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
