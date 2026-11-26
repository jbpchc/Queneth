"""PSGC can run live on its own while email and image hosting stay mocked."""

from app.core.config import Settings
from app.integrations.base import IntegrationName
from app.integrations.psgc import PsgcAdapter


def test_psgc_mode_overrides_the_global_mode():
    s = Settings(integrations_mode="mock", psgc_mode="live")
    assert s.mode_for("psgc") == "live"
    assert s.mode_for("brevo") == "mock" and s.mode_for("cloudinary") == "mock"
    assert PsgcAdapter(s).mock is False
    assert IntegrationName.PSGC.value == "psgc"


def test_blank_psgc_mode_follows_the_global_mode():
    s = Settings(integrations_mode="mock", psgc_mode="")
    assert s.psgc_mode is None and s.mode_for("psgc") == "mock"
    assert PsgcAdapter(s).mock is True
