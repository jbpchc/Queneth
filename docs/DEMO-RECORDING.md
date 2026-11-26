# Screen-recording workflow — Platform Technologies + IPT

One recording that covers **both** rubrics. Each scene says what to show, the
exact commands or clicks, what to say, and which rubric rows it earns.

| Code | Rubric row | Points |
| --- | --- | --- |
| **PT1** | PlatTech · Error-Free Platform Execution on VM | 35 |
| **PT2** | PlatTech · Localhost & VM Network Configuration | 25 |
| **PT3** | PlatTech · VM Provisioning & Environment Setup | 20 |
| **PT4** | PlatTech · Service & Database Reliability | 10 |
| **PT5** | PlatTech · VM Verification & Setup Documentation | 10 |
| **IPT1** | IPT · Core E-Commerce Functionality | 25 |
| **IPT2** | IPT · API Integration & Design (min. 2 APIs) | 25 |
| **IPT3** | IPT · Python Back-End & Database Architecture | 20 |
| **IPT4** | IPT · Virtual Machine & Localhost Environment | 15 |
| **IPT5** | IPT · Front-End UI/UX & Documentation | 15 |

**Target length: 18–22 minutes.** Record in one take if you can; if you cut,
cut between scenes, never in the middle of a command (graders look for
"no manual intervention").

---

## Before you press record (10 minutes)

1. **VirtualBox (VM off):** 4 CPUs, 8192 MB RAM (or what you have), 128 MB video memory.
2. **Laptop:** plugged in, other apps closed, notifications off (Do Not Disturb).
3. **Record from the host, not inside the VM.** It keeps the VM fast.
   - Windows host: **OBS Studio** (best) or **Xbox Game Bar** (`Win + Alt + R`).
   - Capture the VirtualBox window in full screen (`Right Ctrl + F`), 1080p, 30 fps, with your microphone.
4. **Inside the VM**, open a terminal and run:

   ```bash
   cd ~/Queneth
   vm/tune.sh            # once per VM (asks for your password)
   vm/reset.sh           # clean store: 0 orders, 31 products — ends running
   vm/stop.sh            # stop it again so you can start it ON CAMERA
   clear
   ```

5. Open in the VM: **Firefox** (zoom 110%, one empty tab), **one terminal**
   (font size ~14, window half screen), **VS Code** on `~/Queneth`, and the
   **Files** app — nothing else. Close the Claude desktop app.
6. Have this page open on your phone or a second screen as your script.

Accounts (password `Queneth#2026`, PIN `123456`): `buyer@queneth.test`,
`bench@queneth.test`, `admin@queneth.test`.

---

## Scene 1 · Intro (0:00 – 0:45)

**Show:** the Queneth home page screenshot or the README in VS Code.

**Say:** names, project title, one sentence: *"Queneth is a multi-vendor fashion
marketplace with separate buyer, seller and admin accounts, an escrow wallet
(QueWallet), and three external integrations. Everything runs inside this
Ubuntu VM."* Name the stack: FastAPI (Python), SQLAlchemy + SQLite, Next.js.

---

## Scene 2 · The VM and its environment (0:45 – 3:00) → PT3, IPT4

1. Briefly show **VirtualBox → Settings → System** (CPUs, RAM) and **Storage** (disk). Close it.
2. In the VM terminal:

   ```bash
   lsb_release -d; nproc; free -h; df -h ~
   ```

   *"Ubuntu 26.04 guest with 4 vCPUs and 8 GB RAM, running everything — nothing on the host."*

3. Isolated dependencies:

   ```bash
   ls backend/.venv/bin | head -5
   backend/.venv/bin/python --version
   backend/.venv/bin/python -m pip list 2>/dev/null | grep -iE "fastapi|sqlalchemy|uvicorn|pwdlib|httpx"
   node -v; ls frontend/node_modules | wc -l
   cat backend/.env.example | head -20
   ```

   *"Python packages live in an isolated virtual environment, Node in the user
   folder; configuration comes from `.env` files (the real one holds secrets, so I'm showing the template)."*

> Never `cat backend/.env` on camera: it contains the JWT secret.

---

## Scene 3 · Start the services, live (3:00 – 5:00) → PT4, PT2, IPT4

```bash
vm/start.sh --prod
```

While it runs, explain: *"One command checks the VM, starts the FastAPI API on
port 8000, builds and starts the production storefront on port 3000, and runs
them in the background so closing the terminal doesn't stop them."*

Then prove ports and health:

```bash
vm/status.sh
ss -ltnp '( sport = :3000 or sport = :8000 )'
curl -s localhost:8000/api/v1/health; echo
```

*"API and storefront are up, the database answers, both logs are clean — no
port conflicts. Front end on localhost:3000, API on localhost:8000."*

---

## Scene 4 · Documentation (5:00 – 6:00) → PT5, IPT5

In VS Code or the Files app, scroll quickly through:

- `README.md` → *"setup, account types, commands"*
- `docs/VM-SETUP.md` → *"step-by-step VM provisioning and startup, verification checklist, troubleshooting"*
- `docs/RUNNING-QUENETH.md` → *"day-to-day commands and fixes"*
- `docs/INTEGRATIONS.md` → *"each external API, its endpoints, timeouts and fallbacks"*
- `backend/pyproject.toml` → *"pinned Python dependencies"* (and `backend/requirements.txt` if you add one)

Then in Firefox open **http://localhost:8000/docs** → *"Interactive API
documentation, generated from the code: 160+ REST endpoints grouped by area."*
Scroll the groups (auth, catalog, cart, orders, wallet, seller, admin).

---

## Scene 5 · Shopping as a guest (6:00 – 7:30) → IPT1, IPT5, PT1

At **http://localhost:3000**:

1. Home page → **Clothing** → use a **color** or **size** filter → sort by price.
2. Search box: type `nike` (show suggestions) → open a product.
3. Product page: pick a color (the photo switches) and a size; point at the
   stock line (*"In stock · ships in 2–4 days"* / *"Only 3 left"*). The sold-out
   case is shown live in Scene 8.
4. Click **Add to Bag** while signed out → *"guests are asked to sign in; the bag belongs to an account."*
5. Open **/bag** as a guest → empty-bag state.

---

## Scene 6 · Accounts and authentication (7:30 – 9:00) → IPT1, IPT3

1. **Register** → try a weak password and a bad email → show the error messages →
   cancel. *"Inputs are validated on the server, not just in the browser."*
2. **Sign in** as `buyer@queneth.test`.
3. Back in the terminal, show passwords are hashed:

   ```bash
   backend/.venv/bin/python -c "import sqlite3; c=sqlite3.connect('backend/demo.db'); print(c.execute(\"select email, substr(password_hash,1,32) from users where email='buyer@queneth.test'\").fetchone())"
   ```

   *"Only an Argon2id hash is stored, never the password. Sessions use short-lived
   JWT cookies with refresh-token rotation and CSRF protection."*

---

## Scene 7 · Bag, edge cases and checkout (9:00 – 12:00) → IPT1, IPT2, PT1

1. Bench **Pique Polo** → size **M** → **Add to Bag**.
2. Open another product → **Buy now** → *"Buy now pays for just this piece; the bag keeps the rest."*
   Click "Check out the whole bag instead" to return to the full bag.
3. In the **Bag**: raise the quantity above the stock → *"Only N left"*; use
   **Save for later**; type a wrong voucher code → friendly error.
4. **Checkout with QueWallet → Add a new address**: choose **Region →
   Province → City → Barangay**. *"This list comes from the PSGC API — the
   Philippine government's official geographic codes — our first external API."*
5. Review → enter a **wrong PIN** (`111111`) → error, no charge → enter
   `123456` → **Pay**. Confirmation page: *"Paid, held in escrow."*
6. **Account → Orders** → the order and its status timeline (order history).

---

## Scene 8 · Seller and order lifecycle (12:00 – 14:00) → IPT1, PT1

1. Sign out → sign in as `bench@queneth.test` → **Seller Studio**.
2. **Orders** → the new order → *Start preparing* → *Ship* with tracking
   `LBC-12345678` → *Mark delivered*.
3. **Stock** → set the *Pique Polo · Purple · XS* stock to **0** → save.
   Open http://localhost:3000/p/bench-pique-polo: **XS is crossed out** and
   can't be chosen. *"Inventory changes reach the shop instantly; out-of-stock
   options can't be bought."* (Set it back afterwards, or `vm/reset.sh` later.)
4. Quick look at **My products** (draft/live) and **Earnings**.
5. Sign back in as `buyer@` → the order → **I received it** → leave a review.
   *"Escrow is released to the seller minus 5% commission; the buyer earns Que Points."*
6. Point out: sellers have **no bag or wishlist** — the three account types are separate.

---

## Scene 9 · The APIs up close (14:00 – 16:30) → IPT2 (25 pts — don't rush this)

At **http://localhost:8000/docs** ("Try it out"):

1. `GET /api/v1/catalog/products` → **200** with clean JSON (items, pagination).
2. `GET /api/v1/catalog/products/{slug}` with `does-not-exist` → **404** with an error body.
3. `GET /api/v1/cart` → **401** *"protected endpoints need a signed-in session."*
4. `GET /api/v1/geo/regions` → the PSGC data through our API (cached, with offline fallback).

Then in the app, sign in as `admin@queneth.test` → **Control Room → Integrations**:

- Three cards: **PSGC** (addresses), **Brevo** (transactional email), **Cloudinary**
  (images): calls, failures, fallbacks, latency.
- *"Every external call has a 5-second timeout and retries; if a provider is
  down, Queneth falls back (bundled PSGC copy, local image storage, email
  queued) so shoppers never see an outage."*
- **Sent emails** → open the order-confirmation email preview → *"Brevo runs in
  mock mode for the demo, so emails are recorded instead of sent."*

Summarise: *"Our own RESTful API with proper methods and status codes, plus three
external APIs — PSGC, Brevo and Cloudinary — exceeding the two-API minimum."*

---

## Scene 10 · Back-end architecture and database (16:30 – 18:30) → IPT3, PT4

1. VS Code, `backend/app/` — open each folder for 2–3 seconds:
   - `api/v1/routers/` → *"HTTP layer: routes only"*
   - `services/` → *"business logic"*
   - `models/` → *"SQLAlchemy database models with foreign keys and constraints"*
   - `schemas/` → *"Pydantic validation of every request and response"*
   - `alembic/versions/` → *"versioned database migrations"*
2. Open `app/core/permissions.py` → *"role-based permissions: buyer, seller, admin."*
3. Control Room → **QueWallet → Run reconciliation** → **zero drift**:
   *"double-entry ledger; every balance matches its transactions."*
4. **Audit log** → admin actions recorded.

---

## Scene 11 · Clean logs and wrap-up (18:30 – 20:00) → PT5, PT1, PT4

```bash
vm/status.sh
grep -ciE "traceback|error" logs/api.log logs/web.log
```

*"After the whole walkthrough: services still up, zero tracebacks or errors in
the logs."* Optionally run the automated tests (takes ~2 min — fine to speed up in editing):

```bash
cd backend && .venv/bin/python -m pytest -q
```

Close with: what you built, the two rubric highlights (runs fully inside the VM;
own API + three external APIs), and thanks.

---

## Checklist — every rubric row covered

| Row | Shown in scenes |
| --- | --- |
| PT1 Error-free execution | 5, 7, 8, 11 (no errors across all workflows) |
| PT2 Localhost & ports | 3 (`ss`, health check, ports 3000/8000) |
| PT3 VM provisioning | 2 (resources, venv, Node, `.env.example`) |
| PT4 Service & DB reliability | 3, 10, 11 (one-command start, health, reconciliation) |
| PT5 VM docs & clean logs | 4, 11 |
| IPT1 Core e-commerce + edge cases | 5, 6, 7, 8 (empty bag, over-stock, wrong PIN, sold-out size) |
| IPT2 ≥ 2 APIs, status codes, failures | 7, 9 |
| IPT3 Python back-end, schema, hashing, validation | 6, 10 |
| IPT4 VM & localhost | 2, 3 |
| IPT5 UI/UX + README, requirements, API docs | 4, 5–8 |

## If something goes wrong while recording

Don't panic on camera — this is also graded ("handles errors gracefully").

| Problem | Do this |
| --- | --- |
| Page slow on first load | Wait; say "first load after a fresh build". |
| `vm/start.sh` says a port is taken | `vm/stop.sh`, then `vm/start.sh --prod`. |
| Sign-in says "too many attempts" | Wait one minute (login rate limit — mention it's a security feature). |
| Anything else | Stop recording, `vm/reset.sh`, restart from the last scene. |
