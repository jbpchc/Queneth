from fastapi import APIRouter, BackgroundTasks, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import AppSettings, CurrentUser, DbSession, SessionFactoryDep, client_ip
from app.core.errors import AppError, error_body
from app.core.rate_limit import (
    FORGOT_LIMIT,
    LOGIN_LIMIT,
    REFRESH_LIMIT,
    REGISTER_LIMIT,
    RESEND_LIMIT,
    RESET_LIMIT,
    limiter,
)
from app.core.security import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenRequest,
)
from app.services import account_service, auth_service, email_service, user_service, wallet_service
from app.services.auth_service import ClientInfo, IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"])


def _client(request: Request) -> ClientInfo:
    return ClientInfo(ip=client_ip(request), user_agent=request.headers.get("user-agent"))


def _sign_in(
    response: Response, tokens: IssuedTokens, roles: list[str], settings: AppSettings
) -> None:
    set_auth_cookies(
        response, access=tokens.access, refresh=tokens.refresh, roles=roles, settings=settings
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a buyer account and sign in",
    responses={409: {"description": "Email already registered"}},
)
@limiter.limit(REGISTER_LIMIT)
async def register(
    request: Request,
    response: Response,
    body: RegisterRequest,
    session: DbSession,
    settings: AppSettings,
    background: BackgroundTasks,
    session_factory: SessionFactoryDep,
) -> AuthResponse:
    user, tokens = await auth_service.register(session, body, settings, _client(request))
    # 50,000 QC welcome grant through the ledger (spec §8), idempotent per user.
    await wallet_service.grant_welcome(session, user)
    # Queue the confirmation email (and its inbox copy); deliver after the response.
    entry = await account_service.send_verification(session, user, settings)
    await session.commit()
    background.add_task(email_service.deliver, session_factory, entry.id, settings)
    _sign_in(response, tokens, user.roles, settings)
    return AuthResponse(user=user_service.to_me(user))


@router.post("/login", response_model=AuthResponse, summary="Sign in with email and password")
@limiter.limit(LOGIN_LIMIT)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: DbSession,
    settings: AppSettings,
) -> AuthResponse:
    user, tokens = await auth_service.login(session, body, settings, _client(request))
    _sign_in(response, tokens, user.roles, settings)
    return AuthResponse(user=user_service.to_me(user))


@router.post("/refresh", response_model=AuthResponse, summary="Rotate the refresh token")
@limiter.limit(REFRESH_LIMIT)
async def refresh(
    request: Request, response: Response, session: DbSession, settings: AppSettings
) -> AuthResponse | JSONResponse:
    try:
        user, tokens = await auth_service.refresh(
            session, request.cookies.get(REFRESH_COOKIE), settings, _client(request)
        )
    except AppError as exc:
        # A dead refresh token ends the session: clear every cookie so the
        # browser and the Next.js proxy agree the user is signed out.
        failed = JSONResponse(
            status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details)
        )
        clear_auth_cookies(failed, settings)
        return failed
    _sign_in(response, tokens, user.roles, settings)
    return AuthResponse(user=user_service.to_me(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out this device")
async def logout(request: Request, session: DbSession, settings: AppSettings) -> Response:
    await auth_service.logout(session, request.cookies.get(REFRESH_COOKIE), settings)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response, settings)
    return response


@router.get("/session", response_model=AuthResponse, summary="Who am I (alias of GET /me)")
async def session_info(user: CurrentUser) -> AuthResponse:
    return AuthResponse(user=user_service.to_me(user))


@router.post(
    "/verify-email/resend",
    response_model=MessageResponse,
    summary="Email a new confirmation link to the signed-in user",
)
@limiter.limit(RESEND_LIMIT)
async def resend_verification(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    settings: AppSettings,
    background: BackgroundTasks,
    session_factory: SessionFactoryDep,
) -> MessageResponse:
    entry = await account_service.send_verification(session, user, settings)
    await session.commit()
    background.add_task(email_service.deliver, session_factory, entry.id, settings)
    return MessageResponse(message=f"We sent a new link to {user.email}.")


@router.post("/verify-email", response_model=MessageResponse, summary="Confirm an email address")
async def verify_email(body: TokenRequest, session: DbSession) -> MessageResponse:
    # Works signed in or out: the link may be opened on another device.
    user = await account_service.verify_email(session, body.token)
    return MessageResponse(message=f"{user.email} is confirmed.")


@router.post(
    "/password/forgot",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Email a password reset link (same answer whether or not the account exists)",
)
@limiter.limit(FORGOT_LIMIT)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    session: DbSession,
    settings: AppSettings,
    background: BackgroundTasks,
    session_factory: SessionFactoryDep,
) -> MessageResponse:
    entry = await account_service.request_password_reset(session, body.email, settings)
    if entry is not None:
        background.add_task(email_service.deliver, session_factory, entry.id, settings)
    return MessageResponse(
        message="If an account uses that email, a reset link is on its way. It expires in 1 hour."
    )


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    summary="Set a new password with a reset link; signs out every device",
)
@limiter.limit(RESET_LIMIT)
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    session: DbSession,
    settings: AppSettings,
    background: BackgroundTasks,
    session_factory: SessionFactoryDep,
) -> JSONResponse:
    _, email_id = await account_service.reset_password(session, body.token, body.password, settings)
    background.add_task(email_service.deliver, session_factory, email_id, settings)
    response = JSONResponse(
        MessageResponse(message="Password updated. Sign in with your new password.").model_dump()
    )
    clear_auth_cookies(response, settings)
    return response
