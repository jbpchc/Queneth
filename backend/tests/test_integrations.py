"""PSGC and Cloudinary adapters: mock mode, live mode, caching, fallbacks."""

import struct
import uuid
from datetime import timedelta
from urllib.parse import urlparse

import httpx
import pytest

from app.core.config import get_settings
from app.core.security import utcnow
from app.integrations.base import IntegrationName, registry
from app.integrations.cloudinary_client import CloudinaryAdapter, api_sign
from app.integrations.image_sniff import sniff
from app.integrations.psgc import PsgcAdapter, load_snapshot
from app.models import GeoCache, MediaAsset
from app.services.geo_service import INDEPENDENT_LABEL, GeoService

NCR, BICOL, ZAMBOANGA = "130000000", "050000000", "090000000"
CAM_SUR = "051700000"


@pytest.fixture(autouse=True)
def _fresh_registry():
    registry.reset()
    yield
    registry.reset()


def live_settings(**extra):
    return get_settings().model_copy(update={"integrations_mode": "live", **extra})


# ─── PSGC: snapshot / mock mode ────────────────────────────────────────────


def test_snapshot_is_complete():
    snap = load_snapshot()
    assert len(snap.regions()) == 17
    assert sum(len(snap.provinces(r.code)) for r in snap.regions()) == 81
    assert snap.provinces(NCR) == []
    assert len(snap.region_cities(NCR)) == 17


async def test_geo_endpoints_in_mock_mode(client):
    regions = (await client.get("/api/v1/geo/regions")).json()
    assert regions["source"] == "snapshot" and len(regions["items"]) == 17

    provinces = (await client.get(f"/api/v1/geo/regions/{BICOL}/provinces")).json()["items"]
    assert {"code": CAM_SUR, "name": "Camarines Sur"} in provinces

    cities = (
        await client.get(f"/api/v1/geo/regions/{BICOL}/cities", params={"province": CAM_SUR})
    ).json()["items"]
    naga = next(c for c in cities if "Naga" in c["name"])
    barangays = (await client.get(f"/api/v1/geo/cities/{naga['code']}/barangays")).json()["items"]
    assert len(barangays) > 20

    resolved = (await client.get(f"/api/v1/geo/barangays/{barangays[0]['code']}")).json()
    assert resolved["city"] == naga["name"] and resolved["province"] == "Camarines Sur"


async def test_ncr_has_no_provinces_but_has_cities(client):
    assert (await client.get(f"/api/v1/geo/regions/{NCR}/provinces")).json()["items"] == []
    cities = (await client.get(f"/api/v1/geo/regions/{NCR}/cities")).json()["items"]
    assert any(c["name"] == "City of Manila" for c in cities)


async def test_independent_cities_get_a_virtual_province(client):
    provinces = (await client.get(f"/api/v1/geo/regions/{ZAMBOANGA}/provinces")).json()["items"]
    assert provinces[-1] == {"code": ZAMBOANGA, "name": INDEPENDENT_LABEL}
    independent = (
        await client.get(f"/api/v1/geo/regions/{ZAMBOANGA}/cities", params={"province": ZAMBOANGA})
    ).json()["items"]
    assert [c["name"] for c in independent] == ["City of Isabela"]


@pytest.mark.parametrize("bad", ["13", "abc", "1300000000"])
async def test_geo_rejects_malformed_codes(client, bad):
    res = await client.get(f"/api/v1/geo/regions/{bad}/provinces")
    assert res.status_code == 422


# ─── PSGC: live mode, cache and fallback ───────────────────────────────────


def _psgc_transport(calls: list[str], *, fail: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if fail:
            raise httpx.ConnectError("PSGC down")
        if request.url.path.endswith("/regions.json"):
            return httpx.Response(
                200, json=[{"code": "130000000", "name": "NCR", "regionName": "x"}]
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def test_live_psgc_is_cached(db):
    calls: list[str] = []
    settings = live_settings()
    geo = GeoService(db, settings, PsgcAdapter(settings, transport=_psgc_transport(calls)))
    items, source = await geo.regions()
    assert source == "live" and items[0].name == "NCR"
    items, source = await geo.regions()
    assert source == "cache" and len(calls) == 1  # second call never left the server
    assert registry.get(IntegrationName.PSGC).last_success_at is not None


async def test_live_psgc_failure_retries_then_falls_back_to_snapshot(db):
    calls: list[str] = []
    settings = live_settings(integration_retries=2)
    geo = GeoService(
        db, settings, PsgcAdapter(settings, transport=_psgc_transport(calls, fail=True))
    )
    items, source = await geo.regions()
    assert source == "snapshot" and len(items) == 17
    assert len(calls) == 3  # 1 try + 2 retries
    state = registry.get(IntegrationName.PSGC)
    assert state.failures == 1 and state.fallbacks == 1 and "ConnectError" in state.last_error


async def test_live_psgc_failure_prefers_stale_cache(db):
    db.add(
        GeoCache(
            key="regions",
            payload=[{"code": "999999999", "name": "Cached"}],
            fetched_at=utcnow() - timedelta(days=90),
        )
    )
    await db.commit()
    settings = live_settings(integration_retries=0)
    geo = GeoService(db, settings, PsgcAdapter(settings, transport=_psgc_transport([], fail=True)))
    items, source = await geo.regions()
    assert source == "cache" and items[0].name == "Cached"


# ─── Cloudinary signing ────────────────────────────────────────────────────


def test_api_sign_matches_cloudinary_docs_example():
    # Example from Cloudinary's "Generating authentication signatures" guide.
    params = {
        "eager": "w_400,h_300,c_pad|w_260,h_200,c_crop",
        "public_id": "sample_image",
        "timestamp": "1315060510",
        "api_key": "ignored",
        "file": "ignored",
    }
    assert api_sign(params, "abcd") == "bfd09f95f331f558cbd1320e67aa8d488770583e"


def test_upload_response_signature_verification():
    settings = live_settings(
        cloudinary_cloud_name="demo", cloudinary_api_key="k", cloudinary_api_secret="s3cret"
    )
    cloud = CloudinaryAdapter(settings)
    good = api_sign({"public_id": "queneth/avatar/x", "version": 1700000000}, "s3cret")
    assert cloud.verify_upload("queneth/avatar/x", 1700000000, good)
    assert not cloud.verify_upload("queneth/avatar/y", 1700000000, good)
    assert cloud.delivery_url("a/b", "w_100").endswith("/image/upload/w_100/a/b")


# ─── Image sniffing ────────────────────────────────────────────────────────

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    + struct.pack(">II", 640, 800)
    + b"\x08\x02\x00\x00\x00"
    + b"\x00" * 64
)
JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    + b"\xff\xc0\x00\x11\x08"
    + struct.pack(">HH", 500, 400)
    + b"\x03"
    + b"\x00" * 32
)


def test_sniff_detects_type_and_size():
    assert sniff(PNG).content_type == "image/png" and (sniff(PNG).width, sniff(PNG).height) == (
        640,
        800,
    )
    info = sniff(JPEG)
    assert info.content_type == "image/jpeg" and (info.width, info.height) == (400, 500)
    assert sniff(b"<?php echo 1; ?>") is None
    assert sniff(b"GIF89a" + b"\x00" * 40) is None


# ─── Media uploads (local fallback / mock mode) ────────────────────────────


async def _ticket(client, purpose="avatar", **over):
    body = {
        "purpose": purpose,
        "filename": "me.png",
        "content_type": "image/png",
        "size_bytes": len(PNG),
        **over,
    }
    return await client.post("/api/v1/media/uploads", json=body)


async def test_local_upload_flow_sets_avatar(client, accounts, login):
    await login("buyer@queneth.test")
    res = await _ticket(client)
    assert res.status_code == 201, res.text
    ticket = res.json()
    assert ticket["provider"] == "local"
    assert ticket["public_id"].startswith("queneth/avatar/")  # randomized, never the filename

    up = await client.post(
        urlparse(ticket["upload_url"]).path,
        data=ticket["fields"],
        files={"file": ("me.png", PNG, "image/png")},
    )
    assert up.status_code == 200, up.text
    asset = up.json()
    assert asset["status"] == "ready" and asset["width"] == 640

    served = await client.get(urlparse(asset["url"]).path)
    assert served.status_code == 200 and served.content.startswith(b"\x89PNG")

    me = await client.patch("/api/v1/me", json={"avatar_asset_id": asset["id"]})
    assert me.status_code == 200 and me.json()["avatar_url"] == asset["url"]


async def test_upload_rejects_disguised_file(client, accounts, login):
    await login("buyer@queneth.test")
    ticket = (await _ticket(client)).json()
    up = await client.post(
        urlparse(ticket["upload_url"]).path,
        data=ticket["fields"],
        files={"file": ("me.png", b"<script>alert(1)</script>" * 4, "image/png")},
    )
    assert up.status_code == 422 and up.json()["error"]["code"] == "unsupported_image"


@pytest.mark.parametrize(
    ("over", "code"),
    [
        ({"size_bytes": 6 * 1024 * 1024}, "file_too_large"),
        ({"content_type": "image/gif"}, "validation_error"),
        ({"content_type": "application/pdf"}, "validation_error"),
    ],
)
async def test_upload_ticket_validation(client, accounts, login, over, code):
    await login("buyer@queneth.test")
    res = await _ticket(client, **over)
    assert res.status_code == 422 and res.json()["error"]["code"] == code


async def test_upload_ticket_accepts_jpg_alias(client, accounts, login):
    await login("buyer@queneth.test")
    assert (await _ticket(client, content_type="IMAGE/JPG")).status_code == 201


async def test_product_images_need_seller_role(client, accounts, login):
    assert (await _ticket(client, purpose="product")).status_code == 401
    await login("buyer@queneth.test")
    assert (await _ticket(client, purpose="product")).status_code == 403
    await login("seller@queneth.test")
    assert (await _ticket(client, purpose="product")).status_code == 201


async def test_cannot_upload_into_someone_elses_asset(client, accounts, login):
    await login("buyer@queneth.test")
    ticket = (await _ticket(client)).json()
    await login("seller@queneth.test")
    up = await client.post(
        urlparse(ticket["upload_url"]).path,
        data=ticket["fields"],
        files={"file": ("me.png", PNG, "image/png")},
    )
    assert up.status_code == 403  # ticket is bound to the buyer


async def test_avatar_must_be_own_ready_asset(client, accounts, login, db):
    await login("buyer@queneth.test")
    pending = (await _ticket(client)).json()
    res = await client.patch("/api/v1/me", json={"avatar_asset_id": pending["asset_id"]})
    assert res.status_code == 404


async def test_cloudinary_live_flow_verifies_signature(app, client, accounts, login, db):
    settings = live_settings(
        cloudinary_cloud_name="demo", cloudinary_api_key="key", cloudinary_api_secret="s3cret"
    )
    app.dependency_overrides[get_settings] = lambda: settings
    await login("buyer@queneth.test")
    ticket = (await _ticket(client)).json()
    assert ticket["provider"] == "cloudinary"
    assert ticket["upload_url"] == "https://api.cloudinary.com/v1_1/demo/image/upload"
    fields = ticket["fields"]
    assert fields["api_key"] == "key" and "s3cret" not in str(ticket)
    assert fields["signature"] == api_sign(
        {k: v for k, v in fields.items() if k != "signature"}, "s3cret"
    )

    result = {
        "public_id": ticket["public_id"],
        "version": 1731400000,
        "secure_url": f"https://res.cloudinary.com/demo/image/upload/v1731400000/{ticket['public_id']}.jpg",
        "width": 1200,
        "height": 1500,
        "format": "jpg",
        "bytes": 200_000,
    }
    forged = await client.post(
        f"/api/v1/media/uploads/{ticket['asset_id']}/complete",
        json={**result, "signature": "0" * 40},
    )
    assert forged.status_code == 403

    sig = api_sign({"public_id": ticket["public_id"], "version": 1731400000}, "s3cret")
    ok = await client.post(
        f"/api/v1/media/uploads/{ticket['asset_id']}/complete", json={**result, "signature": sig}
    )
    assert ok.status_code == 200
    assert "c_fill" in ok.json()["thumbnail_url"] and "f_auto" in ok.json()["thumbnail_url"]


async def test_browser_side_cloudinary_failure_switches_to_local(app, client, accounts, login, db):
    settings = live_settings(
        cloudinary_cloud_name="demo", cloudinary_api_key="key", cloudinary_api_secret="s3cret"
    )
    app.dependency_overrides[get_settings] = lambda: settings
    await login("buyer@queneth.test")
    ticket = (await _ticket(client)).json()
    fallback = (await client.post(f"/api/v1/media/uploads/{ticket['asset_id']}/fallback")).json()
    assert fallback["provider"] == "local" and fallback["public_id"] == ticket["public_id"]
    asset = await db.get(MediaAsset, uuid.UUID(ticket["asset_id"]))
    assert asset.provider == "local"
    assert registry.get(IntegrationName.CLOUDINARY).fallbacks == 1


async def test_live_mode_without_cloudinary_credentials_uses_local(app, client, accounts, login):
    app.dependency_overrides[get_settings] = lambda: live_settings()
    await login("buyer@queneth.test")
    assert (await _ticket(client)).json()["provider"] == "local"
