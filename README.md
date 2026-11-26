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

### In the Ubuntu VM (one command)

Set up once with **[docs/VM-SETUP.md](docs/VM-SETUP.md)**, then:

```bash
vm/start.sh --prod   # API + storefront in the background; survives closing the terminal
vm/status.sh         # health, VM resources, log check
vm/reset.sh          # clean demo store (0 orders), then start for presenting
vm/tune.sh           # once per VM: lighter Ubuntu (animations, indexer, unused services off)
vm/stop.sh
```

Day-to-day commands, the presentation checklist, speed tips and fixes: **[docs/RUNNING-QUENETH.md](docs/RUNNING-QUENETH.md)**.

### Without Docker (SQLite)

No Postgres or Docker needed; data is kept in `backend/demo.db` between runs. Commands below use the Linux/macOS path `.venv/bin/python`; on Windows use `.venv/Scripts/python`.

```bash
cd backend && .venv/bin/python scripts/run_demo.py
```

```bash
cd frontend && npm run dev
```

This starts a clean marketplace: categories and the admin account only, with no boutiques or products. Add `--demo` to also load the demo boutiques and catalog, `--brands` to add the Nike, Penshoppe and Bench stores (seller logins `nike@`, `penshoppe@`, `bench@queneth.test`) and the shoppers `buyer@` and `collector@queneth.test`, all with the same password, or `--reset` to delete everything and start over.

### Moving your store to another computer or a VM

Your sellers, products and uploaded photos live in `backend/demo.db` and `backend/uploads/`, which Git ignores. `scripts/snapshot.py` packs them into `backend/snapshot/` so they travel with the repo.

On this computer, after changing anything in the app:

```bash
cd backend && .venv/bin/python scripts/snapshot.py save
git add backend/snapshot && git commit -m "Update store snapshot" && git push
```

On the other computer or VM (Python 3.12+ and Node 20+ installed; for the Ubuntu VM follow [docs/VM-SETUP.md](docs/VM-SETUP.md) instead):

```bash
git clone https://github.com/jbpchc/Queneth.git && cd Queneth/backend
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
.venv/bin/python scripts/snapshot.py load      # add --force to replace an existing demo.db
.venv/bin/python scripts/run_demo.py
```

```bash
cd frontend && cp .env.example .env && npm install && npm run dev
```

Then open http://localhost:3000 inside that computer or VM and sign in with the same accounts.

**Opening a VM's site from the host's browser:** use the VM's address (for example `192.168.56.10`) everywhere, *before* running `snapshot.py load` so photo links are rewritten:

- `backend/.env`: `API_PUBLIC_URL=http://192.168.56.10:8000`, `FRONTEND_URL=http://192.168.56.10:3000`, `FRONTEND_ORIGINS=http://192.168.56.10:3000`
- `frontend/.env`: `NEXT_PUBLIC_API_URL=http://192.168.56.10:8000/api/v1`, `NEXT_PUBLIC_SITE_URL=http://192.168.56.10:3000`
- start with `run_demo.py --public` and `npm run dev -- -H 0.0.0.0`, and allow ports 3000 and 8000 through the VM's firewall.

### Demo accounts

**Every account is one of three types**, chosen at sign-up and never mixed:

| Account type | Can | Can't |
| --- | --- | --- |
| **Buyer** | Shop: wishlist, bag, checkout, orders, reviews, follow boutiques, QueWallet top-ups and codes | Sell or open Seller Studio |
| **Seller** | Run one boutique in Seller Studio once approved: products, stock, orders, drops, vouchers, earnings and withdrawals | Shop (no bag, wishlist, checkout or top-ups) |
| **Admin** | Run the marketplace in the Control Room: approve sellers, users, catalog, promotions, wallet tools, audit log | Shop or sell; admins are seeded, never self-registered |

Seed them once (the command is idempotent, so re-running it is safe). Without `--demo` only `admin@queneth.test` and the categories are created:

```bash
docker compose exec api python -m app.seed --demo
```

| Email | Account type | Use it for |
| --- | --- | --- |
| `buyer@queneth.test` | Buyer | Isabela, a creative director, shopping |
| `collector@queneth.test` | Buyer | Marco, a fragrance collector with an order in every status |
| `admin@queneth.test` | Admin | The Control Room (seeded only, never self-registered) |
| `verde@` · `sable@` · `nocturne@` · `ilaya@` · `obra@` · `kintsu@` · `solenne@queneth.test` | Seller | The seven demo boutiques' Seller Studios |
| `ana@` · `rafael@` · `bea@` · `mika@` · `jo@` · `lia@queneth.test` | Buyer | Reviewers in the seed |

Password for all accounts: `Queneth#2026`. QueWallet PIN for every shopper and seller: `123456`. Shoppers start with the 50,000 QC welcome grant (posted through the ledger) and can redeem the codes `QUE-DEMO-5000` and `QUE-WELCOME-1000` on the wallet page. A new seller's wallet starts at 0 and fills with sales released from escrow.

Demo vouchers (one per boutique, once per shopper): `OBRA500` (500 QC off Obra Leather from 5,000 QC), `NOCTURNE15` (15% off Nocturne Parfums from 4,000 QC), `ILAYA-SUN` (1,000 QC off Casa Ilaya from 8,000 QC). `buyer@` has Home (Makati) and Office (Naga) addresses saved.

**Sales:** admins schedule platform sales under **Control Room → Promotions**; boutiques enter pieces under **Seller Studio → Sales**. Shoppers see them on the home page and at `/deals`.

**Your own boutique:** sign up and choose **Open a boutique** (`/register?type=seller`), then send the application that opens next. Sign in as `admin@queneth.test` and approve it under **Control Room → Sellers**; back in the seller account, Seller Studio is open. Buyer accounts can't open a boutique.

With `--demo` the same command seeds the catalog: 5 categories, 7 fictional boutiques, 124 products (curated Unsplash photos with generated-art fallback), 60 reviews, 3 editorial collections and 3 drops (one live, two scheduled). Re-running it changes nothing.

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
| Seed | `cd backend && python -m app.seed` (clean marketplace) or `python -m app.seed --demo` (demo boutiques and catalog) |
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
