import pytest

from app.core.errors import ValidationFailed
from app.core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    clamp_limit,
    decode_cursor,
    encode_cursor,
)


def test_cursor_round_trip():
    pos = {"created_at": "2026-11-12T10:00:00+00:00", "id": "a1b2"}
    assert decode_cursor(encode_cursor(pos)) == pos


def test_empty_cursor_is_first_page():
    assert decode_cursor(None) is None
    assert decode_cursor("") is None


@pytest.mark.parametrize("bad", ["not-base64!!", "W10", "e30x"])
def test_bad_cursor_raises_validation(bad):
    with pytest.raises(ValidationFailed):
        decode_cursor(bad)


def test_clamp_limit():
    assert clamp_limit(None) == DEFAULT_PAGE_SIZE == 24
    assert clamp_limit(0) == 1
    assert clamp_limit(10_000) == MAX_PAGE_SIZE
