# Queneth

*Curated for the connoisseur.*

Queneth is a multi-vendor fashion marketplace for clothing, shoes, bags,
accessories and perfumes, built as an academic capstone. The backend is
100% Python (FastAPI). The Next.js frontend is a client of the REST API only.

> QueWallet credits are simulated for academic purposes and have no cash value.
> All brands, boutiques and products are fictional.

## Stack

| Layer | Tech |
| --- | --- |
| API | Python 3.12+, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2 |
| Database | PostgreSQL 16 (`pg_trgm`, `citext`) |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS v4, Radix, Motion, TanStack Query |
| API types | `openapi-typescript` + `openapi-fetch`, generated from FastAPI's schema |
| Local run | Docker Compose: `db`, `api`, `frontend` |

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

| URL | What |
| --- | --- |
| http://localhost:3000 | Storefront |
| http://localhost:3000/styleguide | Every design token, component and state |
| http://localhost:8000/docs | Swagger UI (ReDoc at `/redoc`) |
| http://localhost:8000/api/v1/health | Health check |

Migrations run automatically when the `api` container starts. To run one by hand:

```bash
docker compose exec api alembic upgrade head
```

### Demo accounts

Seed them once (the command is idempotent, so re-running it is safe):

```bash
docker compose exec api python -m app.seed
```

| Email | Roles | Use it for |
| --- | --- | --- |
| `buyer@queneth.test` | Buyer | Isabela, a creative director, shopping |
| `collector@queneth.test` | Buyer | Marco, a fragrance collector |
| `seller@queneth.test` | Buyer + Seller | Atelier Lumen's Seller Studio |
| `admin@queneth.test` | Admin | The Control Room (seeded only, never self-registered) |

Demo vouchers (one per boutique, once per shopper): `LUMEN10` (10% off Atelier Lumen from 3,000 QC), `OBRA500` (500 QC off Obra Leather from 5,000 QC), `NOCTURNE15` (15% off Nocturne Parfums from 4,000 QC), `ILAYA-SUN` (1,000 QC off Casa Ilaya from 8,000 QC). `buyer@` has Home (Makati) and Office (Naga) addresses saved. `collector@` (Marco) has an order in every status. Other boutique sellers: `obra@`, `ilaya@`, `kintsu@`, `nocturne@`, `solenne@`, `sable@` and `verde@queneth.test` (same password).
| `verde@` · `sable@` · `nocturne@` · `ilaya@` · `obra@` · `kintsu@` · `solenne@queneth.test` | Buyer + Seller | The other seven boutiques |
| `ana@` · `rafael@` · `bea@` · `mika@` · `jo@` · `lia@queneth.test` | Buyer | Reviewers in the seed |

Password for all accounts: `Queneth#2026`. QueWallet PIN for every shopper and seller: `123456`. Each starts with the 50,000 QC welcome grant (posted through the ledger), and the codes `QUE-DEMO-5000` and `QUE-WELCOME-1000` can be redeemed on the wallet page.

The same command seeds the catalog: 5 categories, 8 fictional boutiques, 124 products (801 variants, generated artwork), 60 reviews, 3 editorial collections and 3 drops (one live, two scheduled). Re-running it changes nothing.

### External APIs

PSGC (addresses), Cloudinary (images) and Brevo (email) run in **mock mode** by
default, so everything works offline. Mock emails can be read in Control Room →
Integrations → Sent emails, and users also get a copy in `/account/notifications`.
To go live, see [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md).

### How sign-in works

- The API sets httpOnly JWT cookies: access tokens last 15 minutes, and refresh tokens last 7 days and rotate on every use. The frontend never sees a token. When an access token expires, `src/lib/api/client.ts` refreshes it once and retries the request.
- Mutations send `X-CSRF-Token` (double-submit cookie). Swagger at `/docs` works for GET requests. For mutations, use the frontend or the tests.
- Access is enforced in the API (`require_role`, `require_permission`, and `assert_can` in services). The Next.js proxy (`src/proxy.ts`) only redirects for convenience.
- Roles and permissions live in one file: [`backend/app/core/permissions.py`](backend/app/core/permissions.py).

## Local development without Docker

You still need a PostgreSQL 16 instance. Point `DATABASE_URL` in `backend/.env` at it, or run only the database with `docker compose up db`.

**Backend**

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --reload
```

> **Windows with Smart App Control:** if importing SQLAlchemy fails with
> *"An Application Control policy has blocked this file"*, reinstall it without
> its compiled extensions (same behaviour, pure Python):
>
> ```bash
> DISABLE_SQLALCHEMY_CEXT=1 .venv/Scripts/python -m pip install --force-reinstall --no-deps --no-binary sqlalchemy "sqlalchemy[asyncio]>=2.0,<2.2"
> ```
>
> Run tools as `python -m alembic` / `python -m pytest`, since `.exe` shims may be blocked too.

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

## Everyday commands

| Task | Command |
| --- | --- |
| Backend tests | `cd backend && python -m pytest`. Uses `TEST_DATABASE_URL` (Postgres) when it's reachable, otherwise in-memory SQLite; Postgres-only tests are then skipped |
| Seed demo data | `cd backend && python -m app.seed` |
| Wallet reconciliation | `cd backend && python -m app.scripts.reconcile` (exit 0 = zero drift) |
| Backend lint | `cd backend && python -m ruff check .` |
| New migration | `cd backend && python -m alembic revision --autogenerate -m "add products"` |
| Regenerate the TS API client | `cd backend && python scripts/export_openapi.py && cd ../frontend && npm run gen:api` |
| Frontend type check | `cd frontend && npm run typecheck` |
| Frontend production build | `cd frontend && npm run build` |

## Repository layout

```
backend/    FastAPI app (app/core, app/db, app/api/v1, app/models, app/schemas,
            app/services, app/integrations), Alembic migrations, tests
frontend/   Next.js app (src/app routes, src/components/{ui,layout},
            src/styles/tokens.css, src/lib/api typed client)
docs/       ASSUMPTIONS.md, UX-LAWS.md (API.md, INTEGRATIONS.md, ERD in Phase 11)
```

## API conventions

- All endpoints live under `/api/v1`.
- Every error uses one envelope: `{"error": {"code", "message", "details"}}`.
  Validation errors list `{field, location, message, type}` in `details`.
- List endpoints use cursor pagination: `?cursor=…&limit=24` returns
  `{items, next_cursor, has_more}`.
- Each response carries an `X-Request-ID` header (echoed back if the client sends one).

## Build phases

1. **Foundation** ✅ monorepo, Compose, FastAPI skeleton, error format, Alembic, design tokens, theme, UI primitives, shells, `/styleguide`, typed client
2. **Auth & RBAC** ✅ register/login/refresh/logout, rotating refresh tokens, CSRF, rate limits, `permissions.py` + `can()`, role/permission dependencies, admin roles/bans + audit log, proxy guards, `/403`, login/register/account pages
3. **External API adapters** ✅ PSGC (live + 30-day cache + bundled snapshot), Cloudinary (signed uploads + local fallback), Brevo (queued email + retries + inbox copy), mock mode, admin Integrations page, email verification, password reset
4. **Catalog & discovery** ✅ catalog models + seed, home, listings with facets, typo-tolerant search + autosuggest, product pages with category modules, boutiques, collections, drops, basic wishlist and bag, sitemap
5. **QueWallet** ✅ double-entry ledger with row locks and idempotency keys, welcome grant, simulated top-ups (daily cap), codes, 6-digit PIN with lockout, escrow pay/release/refund primitives, seller withdrawal, admin grant/reverse/codes/reconcile API, wallet page with odometer, history, ledger detail and CSV
6. **Bag & checkout** ✅ PSGC address book, boutique vouchers, save for later, wishlist boards, one-page checkout (address → review → pay with PIN), per-boutique split into escrow with idempotency and price/stock re-checks, confirmation page with confetti, confirmation email, order list and detail
7. **Orders** ✅ explicit sub-order state machine, cancel/ship/deliver/receive, 7-day returns and refunds, escrow release minus 5% (on receipt or auto after 7 days, admin fast-forward), stock and voucher restore, Que Points ledger, status emails, verified reviews with photos, order timeline, seller fulfilment queue, Marco's order history in every status
8. **Seller Studio** ✅ seller application (+ admin approve/reject API), dashboard with 30-day revenue chart, funnel, low stock and first-sale banner, 6-step product wizard with autosaved drafts, drag-to-reorder photos, category details, variants and pricing, bulk archive/restore, duplicate, inventory inline edit, drops with go-live notifications, vouchers, review replies, earnings with simulated withdrawal, storefront settings (featured pieces, lookbook)
9. **Admin Control Room** ✅ overview (GMV, escrow, people, top categories, 30-day chart), seller applications, suspension and featuring, user search with ban/role changes, catalog (categories, subcategories, Connoisseur's picks, collections), shopper reports and moderation, QueWallet tools (balances, reconciliation, grants, codes, ledger reversal, escrow fast-forward), audit log with actors
10. Dopamine & rewards · 11. Polish
