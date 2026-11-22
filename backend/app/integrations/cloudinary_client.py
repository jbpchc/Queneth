"""Cloudinary Upload & Transformation API adapter.

Uploads are *signed* and go straight from the browser to Cloudinary: the API
secret never leaves the backend, and image bytes never pass through it.

Signing (Cloudinary docs, "Generating authentication signatures"): sort the
upload parameters by name, join as `k=v` pairs with `&`, append the API secret,
SHA-1. Upload responses carry `signature = SHA1("public_id=…&version=…" + secret)`,
which we verify before trusting the result.
"""

import hashlib
import hmac
from typing import Any

from app.integrations.base import HttpAdapter, IntegrationError, IntegrationName

#: Parameters Cloudinary excludes from the signature.
_UNSIGNED = frozenset({"file", "api_key", "resource_type", "cloud_name", "signature"})

# Delivery transformations: f_auto picks AVIF/WebP per browser, q_auto tunes quality.
THUMBNAIL = "c_fill,g_auto,w_400,h_500,f_auto,q_auto"


def api_sign(params: dict[str, Any], secret: str) -> str:
    to_sign = "&".join(
        f"{k}={v}" for k, v in sorted(params.items()) if k not in _UNSIGNED and v not in (None, "")
    )
    return hashlib.sha1(f"{to_sign}{secret}".encode()).hexdigest()  # noqa: S324 — Cloudinary's scheme


class CloudinaryAdapter(HttpAdapter):
    name = IntegrationName.CLOUDINARY

    @property
    def configured(self) -> bool:
        return self.settings.cloudinary_configured

    @property
    def upload_url(self) -> str:
        return f"https://api.cloudinary.com/v1_1/{self.settings.cloudinary_cloud_name}/image/upload"

    def signed_upload_fields(self, public_id: str, timestamp: int) -> dict[str, str]:
        """Form fields the browser posts to `upload_url` along with the file."""
        if not self.configured:
            raise IntegrationError(self.name, "not configured")
        params: dict[str, Any] = {
            "public_id": public_id,
            "timestamp": timestamp,
            "allowed_formats": "jpg,png,webp",
            "overwrite": "false",
        }
        signature = api_sign(params, self.settings.cloudinary_api_secret or "")
        return {
            **{k: str(v) for k, v in params.items()},
            "api_key": self.settings.cloudinary_api_key or "",
            "signature": signature,
        }

    def verify_upload(self, public_id: str, version: int | str, signature: str) -> bool:
        if not self.configured:
            return False
        expected = api_sign(
            {"public_id": public_id, "version": version}, self.settings.cloudinary_api_secret or ""
        )
        return hmac.compare_digest(expected, signature)

    def delivery_url(self, public_id: str, transformation: str = "f_auto,q_auto") -> str:
        cloud = self.settings.cloudinary_cloud_name
        return f"https://res.cloudinary.com/{cloud}/image/upload/{transformation}/{public_id}"

    async def ping(self) -> None:
        """Admin API ping (basic auth with key:secret). Used by the status page."""
        if not self.configured:
            raise IntegrationError(self.name, "not configured")
        url = f"https://api.cloudinary.com/v1_1/{self.settings.cloudinary_cloud_name}/ping"

        async def fetch() -> None:
            auth = (
                self.settings.cloudinary_api_key or "",
                self.settings.cloudinary_api_secret or "",
            )
            async with self.client(auth=auth) as client:
                res = await client.get(url)
                res.raise_for_status()

        await self.call("GET /ping", fetch)
