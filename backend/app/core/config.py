"""Application settings, loaded from environment variables (and backend/.env).

Nothing in the codebase hardcodes hosts, ports, or keys; everything flows from
here so the same image runs on a laptop, in Docker Compose, or on a VM.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Real environment variables always win over the file (Docker, VM, CI).
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Runtime
    app_name: str = "Queneth API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://queneth:queneth@localhost:5432/queneth"
    database_echo: bool = False
    test_database_url: str | None = None

    # CORS / frontend
    frontend_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    frontend_url: str = "http://localhost:3000"

    # Auth (used from Phase 2)
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7
    cookie_secure: bool = False
    cookie_domain: str | None = None
    rate_limit_enabled: bool = True

    # Public base URL of this API (used for links to locally stored uploads)
    api_public_url: str = "http://localhost:8000"

    # External integrations
    integrations_mode: Literal["live", "mock"] = "mock"
    #: Per-API override of `integrations_mode` for PSGC (no API key needed), so
    #: the address lists can come from the real service while email and image
    #: hosting stay mocked. Empty: follow `integrations_mode`.
    psgc_mode: Literal["live", "mock"] | None = None
    integration_timeout_seconds: float = 5.0
    integration_retries: int = 2
    psgc_base_url: str = "https://psgc.gitlab.io/api"
    psgc_cache_days: int = 30
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    cloudinary_folder: str = "queneth"
    brevo_api_key: str | None = None
    brevo_base_url: str = "https://api.brevo.com/v3"
    brevo_sender_email: str = "no-reply@queneth.test"
    brevo_sender_name: str = "Queneth"
    email_max_attempts: int = 5
    local_upload_dir: str = "uploads"
    max_upload_bytes: int = 5 * 1024 * 1024

    # Background jobs (APScheduler); disabled in tests
    scheduler_enabled: bool = True

    @field_validator(
        "cloudinary_cloud_name",
        "cloudinary_api_key",
        "cloudinary_api_secret",
        "brevo_api_key",
        mode="before",
    )
    @classmethod
    def _blank_secret_to_none(cls, value: object) -> object:
        return value or None

    @property
    def upload_dir(self) -> Path:
        path = Path(self.local_upload_dir)
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def cloudinary_configured(self) -> bool:
        return bool(
            self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret
        )

    @field_validator("psgc_mode", mode="before")
    @classmethod
    def _blank_is_unset(cls, v: object) -> object:
        return v or None

    def mode_for(self, integration: str) -> Literal["live", "mock"]:
        """The mode one integration runs in ("psgc", "brevo", "cloudinary")."""
        if integration == "psgc" and self.psgc_mode:
            return self.psgc_mode
        return self.integrations_mode

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        # Postel's Law: accept "a,b", "a, b" or a JSON-style list from env.
        if isinstance(value, str):
            return [o.strip().rstrip("/") for o in value.split(",") if o.strip()]
        return value

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        return value or None

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
