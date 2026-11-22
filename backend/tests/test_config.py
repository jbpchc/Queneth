from app.core.config import Settings
from app.core.logging import _redact


def test_frontend_origins_accepts_comma_list():
    s = Settings(frontend_origins="http://a.test, http://b.test/ ,")
    assert s.frontend_origins == ["http://a.test", "http://b.test"]


def test_sensitive_keys_are_redacted():
    out = _redact(None, "info", {"pin": "123456", "password": "x", "user": "isabela"})
    assert out == {"pin": "[redacted]", "password": "[redacted]", "user": "isabela"}
