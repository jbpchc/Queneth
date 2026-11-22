"""Schemas shared across modules: the error envelope, pagination, health."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Base for every request/response schema."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        # In *response* schemas a field with a default is always present, so
        # mark it required there; request schemas keep it optional. This gives
        # the generated TypeScript client exact types in both directions.
        json_schema_serialization_defaults_required=True,
    )


class ErrorDetail(ApiModel):
    code: str = Field(examples=["validation_error"])
    message: str = Field(examples=["Some fields need attention."])
    details: Any = None


class ErrorResponse(ApiModel):
    error: ErrorDetail


class CursorPage[T](ApiModel):
    """A page of results. Pass `next_cursor` back as `?cursor=` for the next page."""

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class HealthResponse(ApiModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: Literal["ok", "unavailable"]
    integrations_mode: Literal["live", "mock"]


# Reusable `responses=` map so error shapes appear in the OpenAPI schema and in
# the generated TypeScript client.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Bad request"},
    401: {"model": ErrorResponse, "description": "Not signed in"},
    403: {"model": ErrorResponse, "description": "Not allowed"},
    404: {"model": ErrorResponse, "description": "Not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}
