"""Cursor pagination shared by every list endpoint.

Cursors are opaque, URL-safe base64 JSON blobs holding the sort key of the last
row returned (e.g. {"created_at": "...", "id": "..."}). Keyset pagination stays
stable while new rows are inserted, unlike OFFSET.
"""

import base64
import binascii
import json
import uuid
from datetime import datetime
from typing import Any

from app.core.errors import ValidationFailed

# UX: Miller's Law — results load in chunks of 24 (a 4×6 / 3×8 / 2×12 grid).
DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 96


def encode_cursor(position: dict[str, Any]) -> str:
    raw = json.dumps(position, separators=(",", ":"), default=str).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise ValidationFailed("That page link is no longer valid.", code="invalid_cursor") from exc
    if not isinstance(data, dict):
        raise ValidationFailed("That page link is no longer valid.", code="invalid_cursor")
    return data


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(limit, MAX_PAGE_SIZE))


def decode_keyset(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    """(created_at, id) cursor used by newest-first lists (orders, seller queue)."""
    pos = decode_cursor(cursor)
    if pos is None:
        return None
    try:
        return datetime.fromisoformat(pos["created_at"]), uuid.UUID(pos["id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValidationFailed("That page link is no longer valid.", code="invalid_cursor") from exc


def encode_keyset(last: tuple[datetime, uuid.UUID] | None) -> str | None:
    if last is None:
        return None
    return encode_cursor({"created_at": last[0].isoformat(), "id": str(last[1])})
