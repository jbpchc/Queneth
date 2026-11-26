# Screen-recording script — Platform Technologies + IPT

Follows the class **SCREEN RECORDING GUIDE** step by step (Steps 1–9), with the
exact Queneth commands, clicks and lines to say. Everything below was rehearsed
in the VM. Target length: **20–25 minutes**.

Accounts — password `Queneth#2026`, QueWallet PIN `123456`:
`buyer@queneth.test` (buyer) · `bench@queneth.test` (seller) · `admin@queneth.test` (admin).

---

## 0. Ten minutes before recording

1. Laptop plugged in, notifications off, heavy apps closed. Record the
   **VirtualBox window from the host** (OBS or `Win + Alt + R`) so the VM stays fast.
2. In the VM, one terminal:

   ```bash
   cd ~/Queneth
   grep -q '^PSGC_MODE=live' backend/.env || echo 'PSGC_MODE=live' >> backend/.env   # live address API (once)
   vm/reset.sh        # clean store: 0 orders, 31 products (also starts Queneth)
   vm/stop.sh         # stop again, so you start it on camera in Step 2
   clear
   ```

3. Open and arrange: **Firefox** (one empty tab), the **terminal** (font ~14),
   **VS Code** on `~/Queneth`. Close the Claude app and anything else.
4. In Firefox, open `about:config` once and set `ui.prefersReducedMotion` to `0`
   (Firefox in a VM turns animations down otherwise).
5. Pick a new email for Step 6, e.g. `demo1@queneth.test` (each email can register once).

---

# Part 1 · Platform Technologies

## Step 1 · VM Provisioning & Environment Setup (20 pts)

1. **VirtualBox Manager** → select the VM → **Settings → System** (Base Memory,
   Processors) → **Storage** (virtual disk size). Close the dialog.
   *"4 vCPUs, 8 GB RAM and a 25 GB virtual disk for the Ubuntu guest."*
2. Switch to the running VM window: *"Everything from here runs inside Ubuntu, not Windows."*
3. In the VM terminal:

   ```bash
   cd ~/Queneth
   lsb_release -d; nproc; free -h; df -h ~
   ls -la backend | grep -E "\.env|\.venv"
   cat backend/.env.example | head -32
   source backend/.venv/bin/activate
   python --version
   pip list
   pip check
   ```

   *"Configuration lives in `.env` files — I'm showing the template because the
   real one contains the JWT secret. Python packages are isolated in a virtual
   environment; `pip check` confirms no missing or broken modules."*
   (Leave the venv active, or run `deactivate`.)

## Step 2 · Localhost & VM Network Configuration (25 pts)

1. **VirtualBox → Settings → Network**: show *Adapter 1*.
   - Our VM uses a **Bridged Adapter**, so it has its own address on the LAN and
     needs no port-forwarding rules; the demo runs in the VM's own browser on
     `localhost`. Say exactly that.
   - (If your VM uses *NAT* instead, show **Advanced → Port Forwarding** with
     Host 3000 → Guest 3000 and Host 8000 → Guest 8000.)
2. In the terminal:

   ```bash
   hostname -I
   ip -brief a
   ```

   *"The VM's internal IP; the app is served on localhost inside the VM."*
3. **Start the services**:

   ```bash
   vm/start.sh --prod
   ```

   *"One command: checks the environment, starts FastAPI on 0.0.0.0:8000, builds
   and starts the Next.js storefront on 0.0.0.0:3000, both in the background."*
4. Prove the ports are listening with no conflicts:

   ```bash
   ss -tulnp | grep -E ':3000|:8000'
   ```

## Step 3 · Service & Database Reliability (10 pts)

```bash
vm/status.sh
curl -i http://localhost:8000/api/health
curl -si http://localhost:8000/docs | head -1
```

*"API, storefront and the SQLite database are up; the health check answers
`200 OK` with `database: ok`, and the API docs page is served."*

## Step 4 · VM Verification, Logs & Setup Documentation (10 pts)

```bash
tail -n 30 logs/api.log
grep -ciE "traceback|error" logs/api.log logs/web.log
```

*"Startup log is clean — zero tracebacks or errors."*

Then open **`README.md`** in VS Code (Ctrl+Shift+V for the preview) and scroll
through **Architecture** and **VM Setup & Startup Instructions**. Mention the
full guide **`docs/VM-SETUP.md`** and **`docs/RUNNING-QUENETH.md`**.

## Step 5 · Error-Free Platform Execution on VM (35 pts)

1. In Firefox (inside the VM) open **http://localhost:3000**.
2. Press **F12** → dock DevTools at the bottom → keep the **Console** tab visible;
   switch to **Network** now and then during Part 2.
   *"No errors in the console and every request returns 2xx — this stays open
   for the whole walkthrough."*

---

# Part 2 · Integrative Programming Technologies

Keep the terminal visible at the side (or Alt+Tab to it) so it's clear the
requests hit the VM.

## Step 6 · Core E-Commerce Functionality (25 pts)

1. **Authentication**
   - **Sign up** → first try a bad email and a short password → the form shows
     clear errors → then register `demo1@queneth.test` / `Queneth#2026`, name *Demo Buyer*.
   - Press **F5**: still signed in (*"JWT in secure cookies, refreshed automatically"*).
2. **Catalog & search**
   - **Clothing** → **More filters** → **Boutique: Bench** (and a size or color)
     → **Show N pieces** → sort by price. *"Filter by vendor, size, color and price."*
   - Search bar: type `jordan` → suggestions → open **Air Jordan 5 'Black Carolina'**.
3. **Bag updates & edge cases**
   - Pick **Black · size 11** (only **3** in stock) → **Add to Bag** → toast.
   - Open the **Bag** (it already warns *"Only 3 left"*) → press **+** to 2, then 3:
     the subtotal updates live (QC 5,495 → 10,990 → 16,485).
   - **Edge case 1 — stock limit:** at 3 the **+** button is disabled, so the bag
     can't exceed the stock. Go back to the product and press **Add to Bag**
     again → error toast *"Only 3 left in this option."*
   - **Edge case 2 — empty bag:** remove the item (trash icon) → *"Your bag is
     empty"* with only *Browse new arrivals*; there is no checkout. Re-add the
     shoe (size 11) from its page for the checkout.
4. **Checkout & order history**
   - **Checkout with QueWallet** → new address: **Region → Province → City →
     Barangay** (from the live PSGC API — see Step 7) → **Save**.
   - **Review** → **Pay**: first-time buyers **choose a 6-digit PIN** (`123456`) →
     **Save PIN** → enter it → type a wrong PIN once to show the error → correct
     PIN → **Pay** → *Order confirmed, held in escrow*.
   - **Account → Orders** → press **F5**: the order is still there (persisted).
   - Stock went down — in the terminal:

     ```bash
     curl -s localhost:8000/api/v1/catalog/products/nike-air-jordan-5-black-carolina | python3 -c "import json,sys; [print(v['options'], 'stock', v['stock']) for v in json.load(sys.stdin)['variants'] if v['options'].get('size')=='11']"
     ```

     (It was 3; now 3 minus what you bought.)

## Step 7 · API Integration Design — Minimum 2 APIs (25 pts)

**API 1 — Queneth's own REST API (FastAPI).** Open **http://localhost:8000/docs**.
You're signed in (same cookies), so *Try it out* works:

| Request | Shows |
| --- | --- |
| `GET /api/v1/catalog/products` → Try it out → Execute | **200** + clean JSON (items, pagination) |
| `POST /api/v1/cart/items` with `{"variant_id": "dc276849-8467-45ac-98e5-e5b93faaecfc", "qty": 1}` | **201 Created**, the updated bag (Pique Polo, Purple · XS) |
| `GET /api/v1/catalog/products/{slug}` with `does-not-exist` | **404** `{"error": {"code": "product_not_found", …}}` |
| `POST /api/v1/cart/items` with `{"variant_id": "abc"}` | **422** validation error JSON (no crash) |

*"Proper methods and status codes; every error is a JSON envelope."*

**API 2 — PSGC, the Philippine government's geographic code API (external, live).**

1. In the storefront: **Account → Addresses → Add an address** → pick a Region and
   Province. In DevTools **Network**, click a `geo/...` request: **200**, JSON with
   `"source": "live"` (or `"cache"` for repeats).
2. In the terminal, the back end's own log of the outbound call:

   ```bash
   grep -E "psgc.gitlab.io" logs/api.log | tail -3
   ```

   *"Our API calls psgc.gitlab.io with a 5-second timeout and retries, caches the
   answer, and falls back to a bundled copy if the service is down."*

**Also integrated (mock mode for the demo):** sign in as `admin@` →
**Control Room → Integrations**: PSGC (live), **Brevo** (transactional email) and
**Cloudinary** (images) with call/failure/fallback counters → **Sent emails** →
open the order-confirmation email preview.

## Step 8 · Python Back-End & Database Architecture (20 pts)

1. **Structure** — VS Code, expand `backend/app/`:
   `api/v1/routers/` (HTTP routes) · `services/` (business logic) · `models/`
   (SQLAlchemy) · `schemas/` (Pydantic validation) · `db/session.py` (database
   connection) · `core/` (security, permissions) · `alembic/versions/` (migrations).
2. **Validation & hashing**
   - `backend/app/schemas/auth.py` → `EmailStr`, password rules.
   - `backend/app/schemas/studio.py` → `VariantIn`: `price_qc: int = Field(gt=0)`, `stock: int = Field(ge=0)`.
   - `backend/app/core/security.py` → line ~21 `Argon2Hasher` (Argon2id hashing).
3. **Schema & persistent data**
   - `backend/app/models/user.py` (users), `catalog.py` (products, variants),
     `commerce.py` (orders → sub_orders → order_items, `ForeignKey(...)`).
   - Terminal:

     ```bash
     sqlite3 -header -column backend/demo.db "SELECT email, substr(password_hash,1,40) AS password_hash FROM users;"
     sqlite3 -header -column backend/demo.db "SELECT number, status, total_qc, created_at FROM orders ORDER BY created_at DESC LIMIT 5;"
     ```

     *"Only Argon2id hashes are stored, and the order we just placed is in the database."*

## Step 9 · Front-End UI/UX & Documentation (15 pts)

1. **Responsive:** DevTools → **Toggle device toolbar** (Ctrl+Shift+M) → iPhone →
   home page and a product page (sticky *Add to Bag / Buy now* bar, bottom tabs).
   Back to desktop.
2. **Feedback:** point at the toasts (*Added to your bag*), button spinners, form
   errors and the empty states you showed.
3. **Documentation** — VS Code, repository root:
   - `README.md` → Architecture, VM Setup & Startup Instructions, **API endpoints**
   - `requirements.txt` → pinned Python dependencies
   - `docs/` → `VM-SETUP.md`, `RUNNING-QUENETH.md`, `INTEGRATIONS.md`
   - live API list: http://localhost:8000/docs

**Close:** `vm/status.sh` once more (*"still up, logs clean"*), then thank the panel.

---

## If something goes wrong on camera

| Problem | Do this |
| --- | --- |
| A page is slow the first time | Wait; *"first load after a fresh build"*. |
| "Port … is taken" | `vm/stop.sh` then `vm/start.sh --prod`. |
| "Too many attempts" at sign-in | Login is limited to 10 per minute — wait 60 s (a security feature). |
| "This email is already registered" | Use the next email (`demo2@…`). |
| Anything else | Stop, `vm/reset.sh`, redo from the last step. |

After recording, `vm/reset.sh` puts the store back to 0 orders.
