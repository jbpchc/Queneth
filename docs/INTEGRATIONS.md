# External API integrations

Queneth integrates **three external APIs**, none of them payment services. All
three are called **only from the Python backend** (`backend/app/integrations/`).
API keys live only in `backend/.env` and are never sent to the browser.

| # | API | Purpose in Queneth | Where it shows in the UI |
| --- | --- | --- | --- |
| 1 | **PSGC API** (Philippine Standard Geographic Code) | Official Region → Province → City/Municipality → Barangay lists | Cascading address dropdowns (`AddressPicker`): style guide now, checkout and address book in Phase 6, seller onboarding in Phase 8 |
| 2 | **Cloudinary** Upload & Transformation API | Signed image uploads, resizing, WebP/AVIF delivery, thumbnails | Account photo now; product wizard, boutique settings and review photos in Phases 7–8; every product image |
| 3 | **Brevo** Transactional Email API | Email verification, password reset and password-changed notices now; order, shipping, seller-approval and drop emails in later phases | User inboxes, plus **Sent emails** in Control Room → Integrations |

## Shared rules (spec §3)

Every adapter extends `HttpAdapter` (`app/integrations/base.py`):

| Rule | Implementation |
| --- | --- |
| Timeout | `httpx.AsyncClient(timeout=INTEGRATION_TIMEOUT_SECONDS)`, default **5 s** |
| Retries | tenacity: **2 retries** (3 attempts), exponential backoff 0.2 → 1.5 s, only on network errors, HTTP 429 and 5xx |
| Logging | structlog events `integration_call` / `integration_failed` with integration, operation, latency; secrets are redacted by the log processor |
| Typed responses | Pydantic models (`PsgcArea`, `CloudinaryResult`, `BrevoSendResponse`) |
| Failure signal | Every failure becomes `IntegrationError`, which callers catch to fall back. It never surfaces as a 500. |
| Status | A process-wide `StatusRegistry` records calls, failures, fallbacks, last success, last error and latency for the admin page |
| Mock mode | `INTEGRATIONS_MODE=mock` (default) never calls the outside world; responses are realistic and the app is fully demoable offline |

**Admin page:** *Control Room → Integrations* (`/admin/integrations`) shows each
API's health (`ok`, `degraded`, `mock`, `unconfigured`, `idle`), mode, last
success, last error, latency, call/failure/fallback counts and per-API details.
In live mode, *Check now* probes the API. The page auto-refreshes every 15 s.

> The status registry lives in memory per API process. With a single Uvicorn
> process (Docker Compose default) the page is exact. With several workers each
> reports its own counters.

---

## 1. PSGC API

**Adapter:** `app/integrations/psgc.py` · **Service:** `app/services/geo_service.py` · **Router:** `/api/v1/geo`

**Live source:** `https://psgc.gitlab.io/api`, a static JSON mirror of the PSA's
PSGC that needs no key. The spec suggested `psgc-api.wareneutron.com`; it returned
HTTP 500 for every request while this was built, so the base URL is configurable
(`PSGC_BASE_URL`) and defaults to the working mirror.

### Endpoints used

| Queneth call | External request |
| --- | --- |
| regions | `GET /regions.json` |
| provinces of a region | `GET /regions/{code}/provinces.json` |
| cities of a region (with `provinceCode`) | `GET /regions/{code}/cities-municipalities.json` |
| barangays of a city | `GET /cities-municipalities/{code}/barangays.json` |
| admin probe | `GET /regions.json` |

Sample external response (`/regions/090000000/cities-municipalities.json`, trimmed):

```json
[
  { "code": "097332000", "name": "City of Isabela", "provinceCode": false,
    "regionCode": "090000000", "isCity": true, "isMunicipality": false }
]
```

### Queneth API (public, browser-cacheable for 24 h)

| Method & path | Returns |
| --- | --- |
| `GET /api/v1/geo/regions` | 17 regions |
| `GET /api/v1/geo/regions/{region}/provinces` | Provinces; `[]` for NCR; plus a virtual **"Independent cities"** entry (code = region code) where a region has cities outside any province (e.g. Isabela City, Cotabato City) |
| `GET /api/v1/geo/regions/{region}/cities?province={code}` | Cities/municipalities of a province; without `province` (NCR) or with the region code: the province-less cities |
| `GET /api/v1/geo/cities/{city}/barangays` | Barangays |
| `GET /api/v1/geo/barangays/{barangay}` | Full place names for a code (used server-side in Phase 6 to validate and snapshot addresses) |

Codes are validated as 9 digits. Sample response:

```json
{ "items": [ { "code": "051700000", "name": "Camarines Sur" } ], "source": "cache" }
```

`source` reports where the answer came from: `live`, `cache` or `snapshot`.

### Caching

Results are stored in the `geo_cache` table (key, JSON payload, `fetched_at`)
for **30 days** (`PSGC_CACHE_DAYS`). The browser also caches each list for the session.

### Fallback

1. Fresh cache → serve it.
2. Otherwise call the live API (with retries).
3. Live call fails → serve the **stale cache** if there is one, else the
   **bundled snapshot**: `app/integrations/data/psgc_snapshot.json.gz`, about
   320 KB, with 17 regions, 81 provinces, 1,634 cities/municipalities and
   42,046 barangays, generated from the same source.

Mock mode serves the snapshot directly.

---

## 2. Cloudinary

**Adapter:** `app/integrations/cloudinary_client.py` · **Service:** `app/services/media_service.py` · **Router:** `/api/v1/media`

The browser uploads **directly to Cloudinary** with a short-lived signature from
the backend. The API secret never leaves the server, and image bytes never pass
through the API.

### Flow

```
Browser                         Queneth API                         Cloudinary
  │ POST /media/uploads ─────────▶ check type (jpg/png/webp) + size ≤ 5 MB,
  │   {purpose, filename,          permission by purpose, random public_id,
  │    content_type, size_bytes}   pending MediaAsset, sign params
  │ ◀──────────── UploadTicket {provider, upload_url, fields, public_id}
  │ POST upload_url (fields + file) ───────────────────────────────────▶ /image/upload
  │ ◀──────────────────────────────────────────── {public_id, version, signature, …}
  │ POST /media/uploads/{id}/complete ▶ verify response signature, mark ready
```

### Endpoints used

| Purpose | External request |
| --- | --- |
| Signed upload (browser) | `POST https://api.cloudinary.com/v1_1/{cloud}/image/upload` |
| Delivery | `https://res.cloudinary.com/{cloud}/image/upload/{transformation}/{public_id}` |
| Admin probe | `GET https://api.cloudinary.com/v1_1/{cloud}/ping` (basic auth key:secret) |

**Signature:** sort the signed params, join them as `k=v` with `&`, append the
secret, then SHA-1. This is unit-tested against Cloudinary's documented example
(`bfd09f95…`). Upload responses are trusted only if
`SHA1("public_id=…&version=…" + secret)` matches their `signature`.

Sample ticket (`POST /api/v1/media/uploads`):

```json
{
  "asset_id": "5b9f…", "provider": "cloudinary",
  "upload_url": "https://api.cloudinary.com/v1_1/demo/image/upload",
  "fields": { "public_id": "queneth/product/3fa8…", "timestamp": "1762934400",
              "allowed_formats": "jpg,png,webp", "overwrite": "false",
              "api_key": "…", "signature": "…" },
  "public_id": "queneth/product/3fa8…", "max_bytes": 5242880
}
```

**Transformations:** `f_auto,q_auto` lets Cloudinary pick AVIF or WebP per
browser. Thumbnails use `c_fill,g_auto,w_400,h_500`. The Next.js image loader
(`frontend/src/lib/image-loader.ts`) adds `w_<width>` for every responsive size,
so Cloudinary does the resizing, not the Next server.

**Security:** images only (JPEG/PNG/WebP) and 5 MB max, checked before signing;
randomized public IDs; product and boutique uploads need `media:upload` (sellers
and admins); avatar and review photos need a signed-in shopper; assets are
owner-scoped; signatures are verified.

### Fallback: local disk

When Cloudinary is in mock mode, has no credentials, or the browser can't reach
it (`POST /media/uploads/{id}/fallback`), the ticket points at
`POST /api/v1/media/uploads/{id}/file` on Queneth itself. That endpoint
re-checks the bytes by magic number (it never trusts `Content-Type`), checks the
size again, reads the dimensions, and saves the file under `LOCAL_UPLOAD_DIR`.
Files are served from `/api/v1/media/files/…`. The browser code is identical for
both providers.

---

## 3. Brevo transactional email

**Adapter:** `app/integrations/brevo_email.py` · **Services:** `email_service.py`, `email_templates.py`, `account_service.py`

### Endpoints used

| Purpose | External request |
| --- | --- |
| Send | `POST https://api.brevo.com/v3/smtp/email` (header `api-key`) |
| Admin probe | `GET https://api.brevo.com/v3/account` |

This is the endpoint the official `brevo-python` SDK wraps. We call it with
async `httpx` because the SDK is synchronous (it would block the event loop),
and this keeps timeouts, retries and status tracking the same across all three
adapters.

Sample request body:

```json
{
  "sender": { "name": "Queneth", "email": "no-reply@queneth.test" },
  "to": [ { "email": "isabela@example.com", "name": "Isabela Reyes" } ],
  "subject": "Confirm your email for Queneth",
  "htmlContent": "<!doctype html>…", "textContent": "Welcome to Queneth…",
  "tags": ["verify_email"]
}
```

Sample response: `201 {"messageId": "<202611121200.123@smtp-relay.mailin.fr>"}`

### Queue, delivery and retries

1. `email_service.queue()` writes an `email_logs` row (`queued`) **and** an
   in-app `notifications` row, in the caller's transaction.
2. A FastAPI **BackgroundTask** delivers it after the response is sent.
3. On failure the row stays `queued` with `next_attempt_at` set by exponential
   backoff (2, 4, 8 … ≤ 60 min). An **APScheduler** job runs every 60 s and
   retries due emails. After `EMAIL_MAX_ATTEMPTS` (5) the row becomes `failed`;
   admins can re-queue it from the Sent emails table.
4. Delivery is idempotent: sent or mocked rows are never sent again.

**Fallback:** the in-app inbox copy (`/account/notifications`) means the
message still reaches the user. The verification link is included there,
because it's the user's own inbox. Password-reset links are not, since they
belong only in the mailbox.

**Mock mode:** no call to Brevo; the email is marked `mocked`. Admins can open
a sandboxed **preview** of mocked emails only. Real deliveries are never
previewable, because they may contain live reset links.

### Email-backed flows (live from Phase 3)

| Flow | Endpoints | Token |
| --- | --- | --- |
| Verify email | sent on register; `POST /auth/verify-email/resend` (signed in, 3 per 10 min); `POST /auth/verify-email {token}` | 48 h, single use, SHA-256 hashed at rest, newer link retires older |
| Password reset | `POST /auth/password/forgot {email}` (always 202, same body: no account enumeration); `POST /auth/password/reset {token, password}` | 1 h, single use; success revokes every session and sends a "password changed" email |

---

## Environment variables (`backend/.env`)

| Variable | Default | Notes |
| --- | --- | --- |
| `INTEGRATIONS_MODE` | `mock` | `live` to call the real APIs |
| `INTEGRATION_TIMEOUT_SECONDS` | `5` | Per request |
| `INTEGRATION_RETRIES` | `2` | Retries after the first attempt |
| `PSGC_BASE_URL` | `https://psgc.gitlab.io/api` | No key needed |
| `PSGC_CACHE_DAYS` | `30` | DB cache lifetime |
| `CLOUDINARY_CLOUD_NAME` / `_API_KEY` / `_API_SECRET` | empty | Free tier is enough; empty means local storage |
| `CLOUDINARY_FOLDER` | `queneth` | Prefix of every public ID |
| `MAX_UPLOAD_BYTES` | `5242880` | 5 MB |
| `LOCAL_UPLOAD_DIR` | `uploads` | Fallback storage (Docker volume `api-uploads`) |
| `API_PUBLIC_URL` | `http://localhost:8000` | Absolute URLs for locally stored images |
| `BREVO_API_KEY` | empty | Free plan: 300 emails/day |
| `BREVO_SENDER_EMAIL` / `BREVO_SENDER_NAME` | `no-reply@queneth.test` / `Queneth` | The sender must be verified in Brevo for live mode |
| `EMAIL_MAX_ATTEMPTS` | `5` | Then `failed` |
| `FRONTEND_URL` | `http://localhost:3000` | Base of emailed links |
| `SCHEDULER_ENABLED` | `true` | Background retry job (off in tests) |

### Going live

1. Create free Cloudinary and Brevo accounts. In Brevo, verify the sender address.
2. Put the keys in `backend/.env` and set `INTEGRATIONS_MODE=live`.
3. Restart the API, open Control Room → Integrations, and press **Check now** on each card.

## Tests

`backend/tests/test_integrations.py` and `test_email_flows.py` cover:

- **Mock mode:** every adapter.
- **Live mode:** `httpx.MockTransport` stands in for the real APIs.
- **Retries:** counted (3 attempts).
- **Fallbacks:** the PSGC snapshot, stale cache, Cloudinary → local, and Brevo failure → queued → failed.
- **Cloudinary signatures:** request and response signing.
- **Upload validation:** a disguised file is rejected, plus the size and type limits.
- **Account flows:** verification and password reset end to end.
- **Admin access:** status page and email log, including 403 for non-admins.
