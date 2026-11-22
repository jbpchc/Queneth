"""CSRF double-submit check for cookie-authenticated mutations (spec §12).

A request that carries an auth cookie and uses an unsafe method must send the
value of the readable `qn_csrf` cookie in the `X-CSRF-Token` header. A
cross-site attacker can make the browser send cookies but cannot read them, so
they can't produce the matching header. SameSite=Lax is the second layer.
"""

import hmac
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.core.errors import error_body
from app.core.security import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, REFRESH_COOKIE

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# These endpoints don't act on the cookie session (they're authorised by the
# request body or a single-use emailed token), so stale cookies mustn't block them.
EXEMPT_SUFFIXES = (
    "/auth/login",
    "/auth/register",
    "/auth/verify-email",
    "/auth/password/forgot",
    "/auth/password/reset",
)


async def csrf_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.method in SAFE_METHODS or request.url.path.endswith(EXEMPT_SUFFIXES):
        return await call_next(request)
    has_session = ACCESS_COOKIE in request.cookies or REFRESH_COOKIE in request.cookies
    if has_session:
        cookie = request.cookies.get(CSRF_COOKIE, "")
        header = request.headers.get(CSRF_HEADER, "")
        if not cookie or not header or not hmac.compare_digest(cookie, header):
            return JSONResponse(
                status_code=403,
                content=error_body(
                    "csrf_failed", "Your session check failed. Refresh the page and try again."
                ),
            )
    return await call_next(request)
