from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.db.session import ping_database
from app.schemas.common import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


async def get_db_pinger():  # overridable in tests
    return ping_database


@router.get(
    "",
    response_model=HealthResponse,
    summary="Liveness and dependency status",
    responses={503: {"model": HealthResponse, "description": "A dependency is down"}},
)
async def health(
    response: Response,
    settings: Settings = Depends(get_settings),
    pinger=Depends(get_db_pinger),
) -> HealthResponse:
    db_ok = await pinger()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        database="ok" if db_ok else "unavailable",
        integrations_mode=settings.integrations_mode,
    )
