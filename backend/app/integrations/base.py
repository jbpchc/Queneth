"""Shared plumbing for every external API adapter (spec §3, integration rules).

- one `httpx.AsyncClient` per call site with a 5 s timeout
- 2 retries with exponential backoff on network errors, 429 and 5xx
- structured logs per call (never the API keys)
- a process-wide status registry the admin Integrations page reads
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import Settings

log = structlog.get_logger(__name__)


class IntegrationName(StrEnum):
    PSGC = "psgc"
    CLOUDINARY = "cloudinary"
    BREVO = "brevo"


class IntegrationError(Exception):
    """An external API failed after retries (or isn't configured). Callers
    catch this and fall back; it never reaches the user as a 500."""

    def __init__(self, integration: IntegrationName, message: str, *, status: int | None = None):
        self.integration = integration
        self.status = status
        super().__init__(f"{integration}: {message}")


@dataclass
class IntegrationState:
    name: IntegrationName
    calls: int = 0
    failures: int = 0
    fallbacks: int = 0
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error: str | None = None
    last_latency_ms: int | None = None
    last_fallback_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class StatusRegistry:
    """In-memory, per API process. Good enough for one Uvicorn process; with
    several workers each reports its own view (see docs/INTEGRATIONS.md)."""

    def __init__(self) -> None:
        self._states = {name: IntegrationState(name) for name in IntegrationName}

    def get(self, name: IntegrationName) -> IntegrationState:
        return self._states[name]

    def all(self) -> list[IntegrationState]:
        return list(self._states.values())

    def success(self, name: IntegrationName, latency_ms: int) -> None:
        s = self._states[name]
        s.calls += 1
        s.last_success_at = datetime.now(UTC)
        s.last_latency_ms = latency_ms

    def failure(self, name: IntegrationName, error: str) -> None:
        s = self._states[name]
        s.calls += 1
        s.failures += 1
        s.last_error_at = datetime.now(UTC)
        s.last_error = error[:300]

    def fallback(self, name: IntegrationName) -> None:
        s = self._states[name]
        s.fallbacks += 1
        s.last_fallback_at = datetime.now(UTC)

    def reset(self) -> None:
        self.__init__()  # type: ignore[misc]

    def snapshot(self) -> list[dict[str, Any]]:
        return [asdict(s) for s in self._states.values()]


registry = StatusRegistry()


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


class HttpAdapter:
    """Base class: builds clients and wraps every request with retry + status."""

    name: IntegrationName

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._transport = transport

    @property
    def mock(self) -> bool:
        return self.settings.mode_for(self.name.value) == "mock"

    def client(self, **kwargs: Any) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.settings.integration_timeout_seconds,
            transport=self._transport,
            **kwargs,
        )

    async def call[T](self, operation: str, fn: Callable[[], Awaitable[T]]) -> T:
        """Run `fn` with retries; record the outcome; raise IntegrationError on failure."""
        started = time.perf_counter()
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.settings.integration_retries + 1),
                wait=wait_exponential(multiplier=0.2, min=0.2, max=1.5),
                retry=retry_if_exception(_retryable),
                reraise=True,
            ):
                with attempt:
                    result = await fn()
        except httpx.HTTPStatusError as exc:
            message = f"HTTP {exc.response.status_code} on {operation}"
            registry.failure(self.name, message)
            log.warning(
                "integration_failed", integration=self.name, operation=operation, error=message
            )
            raise IntegrationError(self.name, message, status=exc.response.status_code) from exc
        except (httpx.HTTPError, ValueError) as exc:
            message = f"{type(exc).__name__} on {operation}"
            registry.failure(self.name, message)
            log.warning(
                "integration_failed", integration=self.name, operation=operation, error=message
            )
            raise IntegrationError(self.name, message) from exc
        latency = int((time.perf_counter() - started) * 1000)
        registry.success(self.name, latency)
        log.info("integration_call", integration=self.name, operation=operation, latency_ms=latency)
        return result
