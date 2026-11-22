"""Column types that use native Postgres features in production and fall back
to portable equivalents elsewhere (the SQLite test fallback, see tests/conftest.py)."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Dialect, String
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB
from sqlalchemy.types import TypeDecorator

#: JSON document column (JSONB on Postgres).
JSONType = JSON().with_variant(JSONB(), "postgresql")

#: Short string array, e.g. user roles (text[] on Postgres, JSON list elsewhere).
StringArray = JSON().with_variant(ARRAY(String(16)), "postgresql")

#: Case-insensitive email (citext on Postgres). Emails are also lower-cased by
#: the Pydantic schemas, so uniqueness holds on every backend.
EmailType = String(320).with_variant(CITEXT(), "postgresql")


class TZDateTime(TypeDecorator[datetime]):
    """Timezone-aware timestamps everywhere. Postgres `timestamptz` already
    returns aware values; SQLite returns naive ones, which are UTC by
    construction, so they're tagged as UTC on load. API responses therefore
    always carry an offset and browsers never misread them as local time."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value
