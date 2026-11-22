"""slowapi limiter shared by every router (login, PIN entry, top-ups, vouchers)."""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.errors import error_body

limiter = Limiter(
    key_func=get_remote_address,
    enabled=get_settings().rate_limit_enabled,
    headers_enabled=False,
)

LOGIN_LIMIT = "10/minute"
REGISTER_LIMIT = "5/minute"
REFRESH_LIMIT = "30/minute"
RESEND_LIMIT = "3/10minutes"
FORGOT_LIMIT = "5/minute"
RESET_LIMIT = "10/minute"
UPLOAD_LIMIT = "30/minute"


async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RateLimitExceeded)
    return JSONResponse(
        status_code=429,
        content=error_body(
            "rate_limited",
            "Too many attempts. Take a breath and try again in a minute.",
            {"limit": str(exc.detail)},
        ),
        headers={"Retry-After": "60"},
    )
