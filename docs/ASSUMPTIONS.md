# Assumptions & decisions

Ambiguities resolved during the build, newest phase last. Each entry says what
was decided and why, so the capstone panel can trace every judgment call.

## Phase 1 — Foundation

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| 1 | Status color shades | Light-mode `--success` #1F9D6B → **#167A53**, `--warning` #B7791F → **#8F5F12**, `--danger` #D4343B → **#C02A31**. | The brief's shades measured 3.23, 3.41 and 4.51:1 on porcelain; WCAG AA needs 4.5:1 for text. The spec says "adjust the shade, never the rule". |
| 2 | Text on Que Magenta (dark) | Added `--on-accent`: white in light mode, near-black #0E0C10 in dark mode. | White on #FF4FA3 is 3.04:1 (fails); ink on it is 6.40:1. Same for `--on-accent-2` on dark cobalt. |
| 3 | Control borders | Added `--border-strong` (#8C8278 light / #7A7182 dark) for inputs, chips and checkboxes. | The spec's `--border` hairline is 1.25:1, which fails WCAG 1.4.11 (3:1) for form controls. Hairlines stay decorative only. |
| 4 | Token names vs Tailwind | Type, radius and shadow tokens are named `--type-*`, `--r-*`, `--elev-*` in `tokens.css`, then mapped to Tailwind's `text-*`, `rounded-*`, `shadow-*` in `globals.css`. | Tailwind v4 owns the `--text-*`/`--radius-*`/`--shadow-*` namespaces; reusing them would create self-referencing variables. |
| 5 | `--dur-celebrate` | Fixed at 900ms (spec gives a 600–1200ms band). | One token value; individual celebrations can scale it within the band. |
| 6 | Framer Motion package | Uses `motion` (`motion/react`), the current name of Framer Motion. | Same library and API; `framer-motion` is now a compatibility re-export. |
| 7 | Dark-mode selector | `next-themes` writes `data-theme` on `<html>` from a blocking script and resolves "system" from `prefers-color-scheme`. | One CSS selector covers both the OS preference and the manual toggle, with no flash of the wrong theme. |
| 8 | Reduced motion | Keyframe loops stop; colour/opacity transitions remain; all transform effects use Tailwind's `motion-safe:` variant; Framer components use `useReducedMotion`. | Spec: "replace movement with opacity fades", not remove all feedback. |
| 9 | Breakpoints | Tailwind `sm/md/lg/xl` = 768/1024/1280/1536px; 360px is the unprefixed mobile base. | Matches the spec's five design widths. |
| 10 | API base URL | Browser uses `NEXT_PUBLIC_API_URL`; server components use `API_INTERNAL_URL` (Compose sets it to `http://api:8000/api/v1`). Calls go directly to FastAPI with CORS + credentials, not through Next rewrites. | Keeps "the frontend is only a REST client" literal. `localhost:3000` and `localhost:8000` are the same *site*, so `SameSite=Lax` auth cookies (Phase 2) still flow. |
| 11 | OpenAPI client generation | `backend/scripts/export_openapi.py` writes `openapi.json` without a running server; `npm run gen:api` turns it into `src/lib/api/schema.d.ts` (openapi-typescript) used by `openapi-fetch`. `npm run gen:api:live` reads it from a running API instead. | Lets the client be regenerated offline and in CI. |
| 12 | OpenAPI URL | Schema served at `/api/v1/openapi.json`; Swagger at `/docs`, ReDoc at `/redoc`. | Versioned schema; docs paths as specified. |
| 13 | Health check | `GET /api/v1/health` returns 200 `ok` or 503 `degraded` with the same body; the DB ping is capped at 1.5s. | Load balancers read the status code; the UI can still show details. asyncpg's default connect timeout is 60s. |
| 14 | IDs | UUID primary keys (`UUIDPrimaryKeyMixin`); human-facing numbers (QN-2026-4821-07) are separate columns. | Unguessable IDs help against IDOR; readable numbers serve Miller's Law. |
| 15 | Postgres extensions | Migration `0001` enables `pg_trgm` (typo-tolerant search) and `citext` (case-insensitive emails). | Needed in Phases 2 and 4; done once up front. |
| 16 | Python version | Docker image uses Python 3.12; local dev verified on 3.13. | Spec says 3.12+. |
| 17 | TypeScript version | Pinned to 5.9.x. | TypeScript 7 (native compiler) is newer than Next's tested range; 5.9 is the safe stable line. |
| 18 | Linting | Backend: ruff. Frontend: `tsc --noEmit` (strict, `noUncheckedIndexedAccess`). | `next lint` was removed in Next 16; a full ESLint setup can be added in Phase 11 if the team wants it. |
| 19 | Boutiques index | Primary nav "Boutiques" links to `/boutiques` (a directory page, added in Phase 4). | The sitemap lists only `/b/[boutique]`, but the nav item needs a destination. |
| 20 | Local Windows dev | On machines with Windows Smart App Control, install SQLAlchemy without C extensions (see README) and run tools as `python -m alembic`, `python -m pytest`. | The policy blocks freshly built `.pyd`/`.exe` files. Docker (Linux) is unaffected. |

## Phase 2 — Auth & RBAC

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| 21 | Cookie set | `qn_access` (httpOnly, path `/`, 15 min), `qn_refresh` (httpOnly, path `/api/v1/auth`, 7 days, rotated), `qn_csrf` (readable, double-submit), `qn_session` (readable, role names only). | Tokens never reach JavaScript. Scoping the refresh cookie to `/api/v1/auth` means it isn't sent on every request. |
| 22 | Session hint cookie | `qn_session` lists role names (e.g. `BUYER.SELLER`) so the Next.js proxy can redirect without the JWT secret. | Proxy guards are UX only (spec §7, layer 3). Forging the hint shows an empty shell; every API call is still authorised server-side (verified: forged `ADMIN` hint → API 403). |
| 23 | Refresh rotation | Every refresh issues a new token and revokes the old one. Tokens from one login share a `family_id`; replaying a rotated token revokes the whole family (`refresh_reused`). | Standard theft detection for long-lived refresh tokens. |
| 24 | CSRF | Unsafe requests that carry an auth cookie must send `X-CSRF-Token` equal to `qn_csrf`. Login and register are exempt. | They don't rely on an existing session, so stale cookies mustn't block them. SameSite=Lax is the second layer. |
| 25 | Swagger and mutations | Swagger `/docs` can call GET endpoints with the browser's cookies; mutations need the CSRF header, so test those with the frontend, curl or the test suite. | No bearer-token side door was added; that keeps one auth path. |
| 26 | Users reloaded per request | `get_current_user` loads the user from the DB on every request instead of trusting JWT role claims. | Bans and role changes apply immediately, not after the 15-minute token expiry. One indexed primary-key lookup per request. |
| 27 | ADMIN via API | `PATCH /admin/users/{id}/roles` accepts only BUYER/SELLER and preserves an existing ADMIN role. Admins can't ban themselves or other admins. | Spec: admins are "seeded only and never self-registered"; also prevents lock-outs. |
| 28 | Sellers can't re-apply | `ROLE_EXCLUSIONS` removes `seller:apply` from anyone holding SELLER, even though they also hold BUYER. | Matrix says "n/a" for sellers. |
| 29 | Ownership | `can(user, perm, resource)` checks `resource.seller_id == user.seller_id`, else `buyer_id`/`user_id`/`owner_id == user.id`. `User.seller_id` stays `None` until Phase 8 adds SellerProfile. | One helper owns all ownership rules (spec §7). |
| 30 | Password policy | 8–128 characters, at least one letter and one number; Argon2id hashing. Login never applies the policy, so older passwords keep working. | Proportionate for an academic project; the strength checklist is shown inline. |
| 31 | `.test` emails | `email-validator` normally rejects the reserved `.test` TLD; it is allowed explicitly. | The spec's demo accounts are `*@queneth.test`. |
| 32 | No account enumeration | Wrong password and unknown email return the same 401 body, and unknown emails still run an Argon2 verify. | Prevents probing which emails are registered. |
| 33 | Test database | Tests use `TEST_DATABASE_URL` (Postgres) when reachable, otherwise in-memory SQLite. Models use portable types (`JSON`→JSONB, `JSON`→`text[]`, `String`→CITEXT on Postgres). Postgres-only tests are marked `@pytest.mark.postgres`. | WSL/Docker weren't available on the dev machine; the suite must still run. Phase 5 wallet concurrency tests will be Postgres-only. |
| 34 | Email verification and password reset | Deferred to Phase 3 (they need the Brevo adapter). `email_verified_at` exists; seeded accounts are pre-verified. | Phase 3 states these "go live here". |
| 35 | Welcome grant | The 50,000 QC grant is added to `auth_service.register` in Phase 5, inside the same transaction. | The ledger arrives in Phase 5. |
| 36 | Rate limits | Login 10/min, register 5/min, refresh 30/min per IP (slowapi, in-memory). `RATE_LIMIT_ENABLED=false` in tests. | In-memory storage is fine for one API process; switch slowapi to Redis if the VM runs several workers. |
| 37 | Production cookie domain | If the API and site are served from different hosts (e.g. `api.example.com` and `example.com`), set `COOKIE_DOMAIN=.example.com` and `COOKIE_SECURE=true`. | Lets the proxy see `qn_session` and the browser read `qn_csrf`. |

## Phase 3 — External API adapters

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| 38 | PSGC source | Default `PSGC_BASE_URL=https://psgc.gitlab.io/api` (static PSA mirror), not `psgc-api.wareneutron.com`. | wareneutron returned HTTP 500 on every request during the build; the spec gives it only as an example. Configurable. |
| 39 | PSGC snapshot | `psgc_snapshot.json.gz` (≈320 KB) bundles all regions, provinces, cities/municipalities and 42,046 barangays, generated from psgc.gitlab.io on 2026-11-12. | Spec: "PSGC falls back to a bundled JSON snapshot". The full set means the offline fallback is never partial. |
| 40 | NCR and independent cities | NCR's provinces list is empty and the picker skips that step. Regions that also have province-less cities get a virtual "Independent cities" province whose code is the region code. | Matches PSGC's real structure, so no city is unreachable. |
| 41 | PSGC cache store | DB table `geo_cache` (30 days). | Survives restarts and is shared by workers; spec allows DB or memory. |
| 42 | Integration status | In-memory `StatusRegistry` per API process. | Lightweight; exact for a single Uvicorn process. Email counts and upload counts on the page come from the DB. |
| 43 | Cloudinary without SDK | Signing and verification implemented directly (documented SHA-1 scheme), tested against Cloudinary's published example. | The official SDK is synchronous; we only need signing. |
| 44 | Upload flow | Browser uploads straight to Cloudinary with a signed ticket. Product/boutique uploads need `media:upload`; avatars/reviews need a signed-in shopper. | Keeps the secret and the image bytes off the API; matches the spec's per-feature roles while `/media` stays "Seller, Admin" for catalog images. |
| 45 | Local fallback trigger | Local storage is used in mock mode, when Cloudinary has no credentials, or when the browser's Cloudinary upload fails (`/fallback`). | The backend can't see a browser-side outage, so the client reports it. |
| 46 | Brevo client | async `httpx` against `POST /v3/smtp/email` instead of the sync `brevo-python` SDK. | The SDK would block the event loop; this also keeps timeouts, retries and status tracking the same for all adapters. |
| 47 | Email storage | Rendered subject/HTML/text are stored in `email_logs` for retries. The API never returns bodies, except admin previews of *mocked* emails. | Real emails can contain live reset links. |
| 48 | Inbox copies | Every email to a user creates a notification. The verification link is included there; password-reset links are not. | Spec fallback ("still saved to the in-app inbox") without putting reset capability in a place a signed-in attacker could read. |
| 49 | Token lifetimes | Verify: 48 h. Reset: 1 h. Single-use, SHA-256 hashed; issuing a new one retires older unused ones. A successful reset also verifies the email and revokes every session. | Standard practice; clicking the reset link proves mailbox ownership. |
| 50 | Unverified users | Can shop normally; a banner nudges them to confirm. | Spec doesn't require verification to buy; friction stays low for demos. |
| 51 | Timezones | `TZDateTime` column type: aware datetimes always; naive values from SQLite are tagged UTC. | Without it, SQLite-backed runs showed "8 hours ago" for new rows in UTC+8 browsers. |
| 52 | Image loader | `next/image` uses a custom loader: Cloudinary `f_auto,q_auto,w_<n>`, Unsplash/Pexels `w,q,auto=format`, local files as-is. | Cloudinary does the resize/format conversion (spec), and Next never re-encodes remote images. |
| 53 | OpenAPI types | `openapi-typescript --default-non-nullable false`. | Request fields with defaults (e.g. `clear_avatar`) must stay optional in the client. |

## Phase 4 — Catalog & discovery

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| 54 | Product imagery | Seed products use **generated, art-directed SVG artwork** (`services/product_art.py`): one silhouette per subcategory drawn in the product's real color, three compositions per product (front, close-up, styled plinth), plus generated boutique logos and banners. Seller uploads via Cloudinary replace them from Phase 8. | The spec allows royalty-free photos *or generated placeholders*. Photo URLs couldn't be verified without an Unsplash/Pexels key; generated art never breaks, needs no internet on the demo VM, and keeps the catalog consistent. |
| 55 | Wishlist & bag in Phase 4 | A minimal wishlist (one list) and bag (add, change qty, remove, grouped by boutique) ship now; boards, save-for-later, vouchers and checkout come in Phase 6. | Product cards and pages need working hearts and Add to Bag; a dead CTA would be a placeholder. Checkout is shown disabled with an explanation. |
| 56 | Boutiques before Seller Studio | `SellerProfile` (boutique) arrives now with 8 approved seed boutiques; the application/approval flow is Phase 8. `User.seller_id` is the boutique id only while it is **approved**. | Products need an owner; ownership rules (spec §7) are now tested against real data. |
| 57 | Search & facets engine | SQL selects the visible catalog (on Postgres pre-filtered by the `pg_trgm` index); typo-tolerant matching, disjunctive facet counts, sorting and keyset cursors run in Python over that set. | One code path on Postgres and the SQLite test DB; fast for a boutique-scale catalog. For tens of thousands of products, move array facets to Postgres (GIN + `&&`). |
| 58 | Typo tolerance | Token match by substring, else fuzzy ratio ≥ 0.78 (difflib), accent-insensitive; the corrected query is returned in `X-Search-Corrected` ("Showing results for…"). | Works identically on every database; covers "bergamt", "neroli". |
| 59 | Denormalized product fields | `min/max_price_qc`, `compare_at_qc`, `total_stock`, `sizes`, `colors`, `facet_values`, `search_text` are recomputed from variants by `catalog_index.refresh_denormalized`. | Listings and facets never load variants. |
| 60 | Visibility | Visible = `status=active`, not deleted, `published_at <= now`, boutique approved. Scheduled-drop products get `published_at = drop.starts_at`, so they 404 until go-live. | Real, not fake, countdowns; no early peeks. |
| 61 | Badges | Only true facts: *New drop*, *Last N left* (real stock ≤ 3), *Sold out*, *Markdown* (real compare-at), *Pre-loved*, *Connoisseur's pick* (one per subcategory). Sold-out pieces sort last. | Spec §6 ethical guardrails. |
| 62 | Seeded social counts | `wishlist_count`, `view_count` and `follower_count` start with plausible historical numbers; real saves and follows increment them. | Trending and boutique cards need non-zero signals on day one. |
| 63 | Variant axes | Clothing size+color; shoes size+color+width (Standard); bags color+size; jewelry/watches metal (+ ring size); belts/hats size; perfumes volume (30/50/100 ml). | Mirrors spec §9. |
| 64 | Currency in JSON-LD | Product schema uses `priceCurrency: "PHP"` with the notional 1 QC = PHP 1 reference. | Schema.org needs an ISO currency; QC is simulated and display-only. |
| 65 | Server rendering & personal state | Catalog pages render on the server anonymously (SEO, fast LCP). Heart, follow and notify state is fetched on the client after hydration. | Keeps SSR cacheable and avoids forwarding user cookies through Next. |
| 66 | Tailwind source scanning | `globals.css` uses `@import "tailwindcss" source(none)` plus `@source ".."`. | Auto-detection keyed off the process cwd; starting the dev server from the repo root silently skipped new files' classes. |
| 67 | Response schemas | `ApiModel` sets `json_schema_serialization_defaults_required`: fields with defaults are required in response types and optional in request types. | Exact generated TypeScript in both directions. |
| 68 | Motion pops | Multi-keyframe pops (heart 1→1.3→1, size chip) use a short back-out tween; springs only for two-keyframe moves. | Motion's spring solver supports only two keyframes. |

## Phase 5 — QueWallet

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| 69 | System wallets | ISSUANCE (source of all minted credits; the only wallet allowed below zero), ESCROW, PLATFORM_REVENUE, OUT_SIMULATED. Created by migration 0005 and on demand. | With ISSUANCE as the counterparty for grants and top-ups, the sum of every balance is always exactly 0, which `reconcile()` checks. |
| 70 | Escrow release = two transactions | ESCROW_RELEASE (escrow → seller, gross − 5%) and COMMISSION (escrow → platform, 5%), posted together. | Both spec transaction types appear in the ledger, and each stays a simple two-leg movement. |
| 71 | Commission rounding | `(gross × 500 + 5,000) // 10,000`: 5% rounded half up to whole QC, integer math only. | No floats anywhere (spec §8). |
| 72 | Locking | `post()` flushes, then `SELECT … FOR UPDATE` every wallet involved, ordered by id. | Prevents overdrafts under concurrency and deadlocks between opposite transfers. The flush keeps pending edits from being discarded by the locking re-read (bug found and regression-tested). |
| 73 | Transactions | `atomic(session)` commits on success and rolls back on any error, whether or not a transaction is already open. | Request sessions usually have one open already (the auth dependency), so a bare `session.begin()` would fail. |
| 74 | Idempotency | Money POSTs take an `Idempotency-Key` header, namespaced per user and action server-side (`topup:{user}:{key}`). Replays return the original transaction; the same key with a different amount returns 409 `idempotency_key_reused`; a concurrent duplicate that loses the unique-constraint race returns the winner's transaction. Welcome grants and code redemptions use natural keys. | Spec §8: a double-click on Pay can't charge twice. |
| 75 | Immutability | `ledger_entries` has a Postgres trigger that rejects UPDATE/DELETE; corrections are REVERSAL transactions with `reverses_id` (unique, so at most one reversal). Reversing a reversal is refused. | The audit trail can't be rewritten. |
| 76 | Daily top-up cap | 50,000 QC of TOPUP per Asia/Manila calendar day (UTC+8, fixed offset). Welcome grants, codes and admin grants don't count. Presets: 1,000 / 5,000 / 10,000. | Matches the spec; fixed offset avoids needing tzdata on Windows. |
| 77 | PIN | Argon2-hashed, 6 digits (spaces tolerated). 5 wrong tries lock the wallet for 15 minutes; failed attempts are committed even though the request fails. Required for withdrawals now and payments in Phase 6; not for adding credit. | Spec §8 and §12. |
| 78 | Codes | Normalized (`" que demo-5000 "` → `QUE-DEMO-5000`); one redemption per user per code; `used_count` incremented under a row lock with `CHECK used_count <= max_uses`. | Postel's Law, and no over-redemption under load. |
| 79 | Pending (escrow) for sellers | The wallet API returns `pending_qc = 0` until orders exist (Phases 6–7 compute it from held sub-orders). | Escrow is one platform wallet; per-seller pending comes from orders. |
| 80 | Admin wallet UI | The admin endpoints (system balances, reconcile, grants, codes, ledger, reversal) ship and are tested now; the Control Room screens arrive in Phase 9. | Keeps the phase plan; demo credits can already be issued via `/docs` or the seed codes. |
| 81 | Notifications | Grants, top-ups and redemptions add an in-app "wallet.credited" notification (no email). | Feedback without notification spam (spec §6). |
| 82 | Overflow clip | Decorative cards use `overflow: clip`, not `hidden`. | A `hidden` box is still a scroll container; focus restoration scrolled the wallet card's content out of view. |

## Phase 6 — Bag & checkout

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| 83 | Address names | The client sends only the PSGC barangay code; region, province, city and barangay names are resolved server-side from the bundled snapshot. Phones are normalized to `+63…` (accepts `0917 123 4567`, `+63 917-…`, `9171234567`). Up to 10 addresses; the first is the default; deleting the default promotes the oldest. | Consistent, valid addresses with no misspelled places (Tesler's and Postel's Laws). |
| 84 | Editing an address | The saved area is kept unless the buyer taps "Change area", which reopens the cascading picker. | PSGC codes don't reliably encode the province/NCR district, so pre-filling the picker from a barangay code would be fragile. |
| 85 | Vouchers | Seller-funded, one per boutique in the bag; percent (floored) or fixed (capped at the boutique's items). Codes are case/space-insensitive. Once per buyer; `used_count` is checked under a row lock at checkout. A voucher below its minimum spend stays applied with "Add X QC more"; at checkout it simply doesn't apply. | Spec §11; the same `voucher_service.evaluate` prices the bag and the checkout, so they can't disagree. |
| 86 | Save for later | A flag on the bag line: excluded from totals and checkout; adding the same variant again moves it back into the bag. | Keeps intent without inflating the total. |
| 87 | Checkout order of operations | Idempotency lookup → address ownership → PIN (wrong tries committed) → atomic block: lock bag variants `FOR UPDATE` (ordered by id) → re-check visibility, stock, own-boutique rule → lock vouchers → compare totals → balance check → create order/sub-orders/items/events → decrement stock → redeem vouchers → one escrow PAYMENT per sub-order → clear bought lines and used vouchers → refresh denormalized stock → queue email and notifications. | All-or-nothing; nothing is charged unless every step succeeds. |
| 88 | Price changes | The client sends `expected_total_qc`; any difference returns 409 `prices_changed` with the new total, and the page returns to Review. | The buyer is never charged a total they didn't see. |
| 89 | Idempotency | `Idempotency-Key` header, scoped `checkout:{user}:{key}`, unique on `orders`. A replay returns the first order; a concurrent duplicate that loses the insert race also returns the winner. The page keeps one key per attempt and only rotates it after a definite server answer (not after a network error). | A double-clicked or retried Pay can't charge twice. |
| 90 | Order numbers | `QN-YYYY-NNNN` (random, collision-checked; widens to 5–6 digits if busy), sub-orders `-01`, `-02` … ordered by boutique name. | Short enough to read aloud (Miller's Law). |
| 91 | Commission & points | Each sub-order stores its 5% commission at checkout (released in Phase 7). `points_pending = total // 100` (1 Que Point per 100 QC), credited on delivery in Phase 7. | Spec §10–11. |
| 92 | Snapshots | Orders store the address and each item's title, brand, options, image and price at purchase time. | Later edits to listings or addresses never rewrite history. |
| 93 | Checkout layout | `/checkout` lives outside the storefront shell: logo and "Secure checkout" only. One page, three collapsible steps, no modals; a sticky Pay bar on step 3. Not enough QC shows an inline top-up panel; no PIN yet shows an inline "set PIN". | Hick's Law and Tesler's Law; the buyer never loses their place. |
| 94 | Confetti | Fires once per order per browser session (sessionStorage flag) and never with `prefers-reduced-motion`. | Peak-End rule without becoming noise. |
| 95 | PIN input | Builds on the latest digits via a ref and accepts multi-digit input (OTP autofill, fast typing); `maxLength` removed because it truncated autofill to one digit. | Found during browser verification. |
| 96 | Orders pages | `/account/orders` (list, keyset pagination) and `/account/orders/[id]` (per-boutique breakdown, payment, delivery). The status timeline and buyer actions arrive in Phase 7. | Keeps the phase plan. |

## Phase 7 — Orders & fulfilment

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| 97 | State machine | `fulfilment_service.TRANSITIONS` is the only source of legal moves (spec §11), each with the actor kinds allowed (buyer, seller, admin, system). Anything else is 409 `invalid_transition`; a wrong actor is 403 `transition_not_allowed`; strangers get 404. Repeating a move that already happened is a no-op. | One explicit map, tested directly; a double-clicked "Received" can't release escrow twice. |
| 98 | Concurrency | Each transition locks the sub-order row `FOR UPDATE` and runs money, stock, event, rollup and notifications in one transaction. | Two people (or the clock and a person) can't move the same order at once. |
| 99 | Escrow | COMPLETED → `release_escrow` (seller gets subtotal − 5%, commission to PLATFORM_REVENUE); CANCELLED/REFUNDED → `refund_escrow` of the sub-order subtotal. Ledger keys are per sub-order (`sub:{id}`, `sub:{id}:refund`). | Spec §8 steps 3–4; idempotent ledger movements. |
| 100 | Stock & vouchers | Cancelling or refunding restores the variants' stock (row-locked) and refreshes product stock; it also frees the voucher (redemption deleted, `used_count` − 1). | Spec: stock restored on cancellation/refund; a refunded buyer shouldn't lose a once-only voucher. |
| 101 | Tracking | Required for SHIPPED: 6–40 letters, digits or dashes, normalized to upper case. The seller UI pre-fills a simulated `QNX-NNNN-NNNN` (regenerable). | No real courier integration in scope. |
| 102 | Returns | Buyer only, within 7 days of `delivered_at`, reason ≥ 10 characters. Seller approves (REFUNDED) or declines (COMPLETED, note required); admin can override. | Spec §11. |
| 103 | Auto-release | APScheduler job every 15 min completes DELIVERED sub-orders older than 7 days as the system (event `actor_id` NULL). Admin `POST /admin/orders/release-due?fast_forward=true` releases all delivered now (audit-logged); the Control Room button arrives in Phase 9. | Spec §8 step 3 and the demo "fast-forward" tool. |
| 104 | Que Points | 1 point per 100 QC of each COMPLETED sub-order, written to an append-only `points_entries` ledger (unique per sub-order) and cached on `users.que_points`. Order pages show earned vs pending. Redemption and tiers arrive in Phase 10. | Spec §6: points are ledgered like the wallet. |
| 105 | Rollup | Parent status = the first active sub-order status in the order RETURN_REQUESTED, PAID, PROCESSING, SHIPPED, DELIVERED; when all are finished: CANCELLED if all cancelled, REFUNDED if all refunded, else COMPLETED. | What needs attention shows first. |
| 106 | Notifications | Buyer gets email + inbox for shipped, delivered, cancelled, refunded and a declined return; in-app only for "preparing" and "completed". Sellers get in-app notices when the buyer cancels or requests a return and when escrow is released. | Status emails (spec Phase 7) without notification spam. |
| 107 | Reviews | Verified purchase only: the buyer of a DELIVERED/COMPLETED line, once per order item (unique `reviews.order_item_id`). Up to 4 review photos via the media flow (Cloudinary or local fallback). Product rating average/count recomputed on create. Fit is asked only for items with a size option. Seller replies arrive in Phase 8. | Spec §10–11. |
| 108 | Seller queue | `/seller/orders` lists only the boutique's own sub-orders with status counts, keyset pagination and the moves the state machine allows. Phase 8 adds the dashboard around it. | Sellers must be able to fulfil for Phase 7 to work end to end. |
| 109 | Seeded history | `collector@queneth.test` (Marco) has 8 orders, one in every status, created through the real checkout and transitions so the ledger reconciles. Seller logins: `obra@`, `ilaya@`, `kintsu@`, `nocturne@`, `solenne@`, `sable@`, `verde@queneth.test` (same password). | Spec §13 demo data. |

## Phase 8 — Seller Studio

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| 110 | Applying to sell | Any shopper can apply at `/account/sell` (name, bio ≥ 40 chars, return policy, contact, city, optional logo/banner). Names are unique case-insensitively; the slug is derived. A pending application can be edited; a rejected one is resubmitted as pending. Boutique uploads need only `profile:manage`, so applicants can add a logo before approval. | Spec §10; one short form. |
| 111 | Approval API now, screen in Phase 9 | `GET /admin/sellers/pending`, `POST /admin/sellers/{id}/approve` (adds the SELLER role) and `/reject` (reason required) ship, are audit-logged and email the applicant. The Control Room screen arrives in Phase 9. After approval the applicant's Studio access starts on their next token refresh; the "Open Seller Studio" button refreshes it immediately. | Phase plan; the flow is usable and tested end to end. |
| 112 | Wizard & drafts | Step 1 (Basics) creates a `draft`; every later change autosaves (debounced ~1 s) via `PATCH`. Drafts may hold partial category details (only known fields are kept); publishing requires description ≥ 40 chars, ≥ 1 photo, ≥ 1 priced variant and valid category details, and the API returns the exact missing list. Live pieces must stay complete and can't change category (duplicate instead). Draft slugs follow the title; live slugs never change. | Spec §10 wizard; URLs stay stable for shoppers. |
| 113 | Variants | Options must use the category's axes (spec §9). Duplicate option combinations are rejected; compare-at must exceed price (genuine markdowns only). New variants get generated SKUs. A variant that was ever ordered can't be deleted (set stock to 0). Price is entered alongside stock so new rows save immediately; the Pricing step handles markdowns. | Order history references variants; found in browser testing that unpriced rows couldn't save. |
| 114 | Images | Gallery order is the order sent (first = cover), with drag-to-reorder plus arrow buttons for keyboard users. Images are either new uploads (owned, ready assets of purpose `product`) or existing URLs of that product; anything else is rejected. | Prevents attaching other people's uploads. |
| 115 | Duplicate / archive / delete | Duplicate copies everything as a draft with stock 0 and fresh SKUs. Archive/restore are bulk; restored pieces go live again only if complete. Only drafts can be deleted (soft delete). | No phantom inventory; published history is kept. |
| 116 | Dashboard | Today's sales and the 30-day chart use Manila calendar days and exclude cancelled/refunded sub-orders. The funnel uses lifetime counters (views, wishlists, a new `bag_add_count`, orders). Top pieces = 30-day revenue. Low stock = live variants at or below their alert level. | Spec §10; honest numbers only. |
| 117 | Revenue chart | Single-series bar chart in the `accent-2` token (validated ≥ 3:1 on both surfaces with the dataviz validator), hover/focus tooltip, rounded data ends, 2px gaps, and a "Show as table" view. | Dataviz method; accessible without color. |
| 118 | First sale | The "Your first sale" banner (with one confetti burst, skipped for reduced motion) shows until dismissed (`first_sale_seen_at`). | Spec §6 peak moment, never repeated. |
| 119 | Earnings | Available = the seller's QueWallet balance (it also holds the welcome credit). In escrow = Σ(subtotal − commission) of PAID…RETURN_REQUESTED sub-orders, also returned as `pending_qc` on the wallet summary. Withdrawals reuse the Phase 5 PIN-confirmed simulated payout. | Spec §8 "Pending vs Available" for sellers. |
| 120 | Drops | Pieces must be complete drafts or live pieces and not in another upcoming drop. Scheduling sets them `active` with `published_at = starts_at`, so they stay hidden until go-live. Drops start ≥ 5 minutes ahead and can be edited or cancelled only while scheduled; cancelling returns their pieces to drafts. A scheduler job (every 60 s) emails "Notify me" subscribers once at go-live. | Real countdowns, no early peeks (spec §6). |
| 121 | Vouchers | Codes are global and normalized (" mira 15 " → MIRA15); percent 1–90 or fixed QC; optional minimum spend, uses and dates. Pausing is allowed anytime; used vouchers can't be deleted (they stay on record). | Spec §10–11. |
| 122 | Review replies | Sellers reply (or edit the reply) to reviews of their own pieces; the first reply notifies the reviewer in-app. Replies already show on product pages. | Spec §10. |
| 123 | Storefront settings | Logo, banner, about, return policy, contact, city, up to 4 featured live pieces (shown first on `/b/[boutique]`) and a 6-image captioned lookbook. | Spec §10 "banner, featured products, lookbook". |

## Phase 9 — Admin Control Room

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| 124 | Reports | Any signed-in shopper can report a live product or a published review (counterfeit, misleading, offensive, spam, other + optional note). One open report per person per item (partial unique index); repeats are absorbed silently. You can't report your own piece or review. | Spec §10 "flagged products and reviews" needs a source of flags. |
| 125 | Moderation outcomes | Reports are grouped per item, most-reported first. Keep it up = dismiss; take down = product status `removed` / review status `hidden`; restore puts it back. Every decision resolves all open reports on the item, notifies the owner (seller or reviewer) and is audit-logged. Hidden reviews drop out of product ratings immediately. | One decision per item, not per report. |
| 126 | "removed" status | A taken-down product can't be republished or restored from Seller Studio (publish returns 409 `product_removed`; bulk restore skips it). Only an admin restore brings it back. Studio labels it "Taken down". | Sellers can't undo moderation. |
| 127 | Suspension | Suspending an approved boutique (reason required) hides its storefront and pieces and closes its Studio (it no longer counts as an approved seller). Open orders keep their escrow; admins can still move them. Reinstating restores everything. The owner is notified both ways. | Spec §10 "suspend sellers" without stranding buyers' money. |
| 128 | User search | Case-insensitive name/email search with role and status filters and offset paging (20 per page). Admin accounts and your own account can't be banned or re-roled from the UI (the API already refuses granting ADMIN). | Spec §10; offset paging suits an admin table with a total count. |
| 129 | Catalog editing | Category name, tagline and order are editable; attribute schemas are shown read-only (they are defined in code and validated by Pydantic). Subcategories can be added, renamed and reordered; renames keep the slug so links never break. Subcategories still used by products can't be deleted. | Stable URLs; schemas must match the validators. |
| 130 | Featured slots | One Connoisseur's pick per subcategory (choosing one clears the previous; only live pieces). Boutiques are featured from the Sellers page; collections are featured on the home page by a flag. Collections are tag-driven: a collection shows live pieces with its tag. | Spec §9 and §10; one true pick avoids diluting the badge. |
| 131 | Overview | GMV = Σ sub-order subtotals excluding cancelled/refunded; 30-day series by Manila day; active buyers = distinct buyers with an order in 30 days; escrow and platform revenue are the system wallet balances. | Honest numbers from the ledger and orders. |
| 132 | Audit actor | The audit log API now returns the actor's "Name <email>" (or System). | Readable accountability without extra lookups. |
| 133 | Wallet tools UI | The Phase 5 admin wallet endpoints and the Phase 7 escrow fast-forward now have a screen: balances, reconciliation, grants (idempotency key per attempt), codes, ledger with type filter and reversal with reason. | Completes spec §10 QueWallet admin. |

## Demo photography

| # | Topic | Decision | Why |
| --- | --- | --- | --- |
| 134 | Real photos for the demo catalog | Curated Unsplash photos (free license, no attribution required; Unsplash+ excluded) replace the generated SVG art for product gallery shots, boutique banners, category covers and collection/drop heroes. Applied by an idempotent seed step (`app/seed/photos.py` → `apply_photos`). Credits in `docs/CREDITS.md`. | Requested by the project owner; a more convincing demo. |
| 135 | Fictional brands only | Every photo was checked by eye and any showing a real brand (logo, label, signature bottle shape) was dropped. | Spec: all brands are fictional. |
| 136 | Linked, with offline fallback | Photos load from images.unsplash.com (nothing added to the repo). Each URL carries its SVG art in an `fb=` parameter; one client listener (`components/layout/image-fallback.tsx`) swaps to it when the CDN fails, including images that failed before hydration. Images without `fb` fall back to `/fallback-art.svg`. | Works in offline demos and defenses without broken-image icons. |
| 137 | Color variants | A product's 3 main shots are photos (no color tag); the primary color keeps its color-correct SVG shot right after them, and other colors keep their SVG shots. The gallery no longer jumps to the preselected color on load, so it opens on the cover photo. | Stock photos can't match every variant color; swatches must never show the wrong color. |
| 138 | Pool rotation | 3–5 photos per subcategory; products rotate through the pool so neighbours in a grid start on different photos. Some photos repeat across products in the same subcategory. | Enough variety without hundreds of curated images. |
