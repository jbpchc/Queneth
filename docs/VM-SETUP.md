# Running Queneth in the Ubuntu VM

Step-by-step setup, start-up and verification for the Platform Technologies
demo. Everything runs **inside the VM**: the FastAPI back end, the SQLite
store database and the Next.js storefront. Nothing runs on the host.

| | |
| --- | --- |
| Guest OS | Ubuntu 26.04 LTS (64-bit), VirtualBox with Guest Additions |
| Resources used for the demo | 2 vCPU · 5.3 GB RAM · 25 GB disk |
| Recommended | **4 vCPU · 8 GB RAM** · 25 GB disk (faster builds and first page loads) |
| Python | 3.12 or newer (the VM has 3.14) in an isolated `backend/.venv` |
| Node.js | 22 LTS, installed in `~/.local/node` (no root needed) |
| Database | SQLite file `backend/demo.db`, loaded from `backend/snapshot/` |
| Ports | 8000 = API (bound to `127.0.0.1`), 3000 = storefront |

---

## 1. Allocate the VM's resources (host side, VM powered off)

VirtualBox → select the VM → **Settings**:

1. **System → Motherboard**: Base Memory **8192 MB** (minimum 4096).
2. **System → Processor**: **4** CPUs (minimum 2).
3. **Storage**: 25 GB disk is enough (Queneth needs about 2 GB).
4. **Network → Adapter 1**: *NAT* is enough when you demo inside the VM.
   Use *Bridged Adapter* only if the site must be opened from another machine
   (see [section 9](#9-optional-open-the-site-from-the-hosts-browser)).

Start the VM and check from a terminal:

```bash
nproc && free -h && df -h ~
```

## 2. System packages (once)

```bash
sudo apt update
sudo apt install -y git curl python3-venv python3-pip
```

`python3-venv` gives Python its `ensurepip` module. Without it,
`python3 -m venv` creates an environment with no `pip`.

## 3. Get the code and set up the back end

```bash
cd ~
git clone https://github.com/jbpchc/Queneth.git   # or git@github.com:jbpchc/Queneth.git with an SSH key
cd ~/Queneth/backend
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))')|" .env
.venv/bin/python scripts/snapshot.py load        # the store: sellers, 31 products, photos
```

All Python packages live in `backend/.venv`; nothing is installed system-wide.

> **No sudo?** Create the environment without pip and bootstrap it instead:
> `python3 -m venv --without-pip .venv && curl -sSL https://bootstrap.pypa.io/get-pip.py | .venv/bin/python`

## 4. Node.js 22 LTS (once, no root needed)

```bash
V=$(curl -s https://nodejs.org/dist/index.json | python3 -c "import json,sys; print(next(r['version'] for r in json.load(sys.stdin) if r['lts'] and r['version'].startswith('v22')))")
mkdir -p ~/.local/node
curl -sSL "https://nodejs.org/dist/$V/node-$V-linux-x64.tar.xz" | tar xJ -C ~/.local/node --strip-components=1
echo 'export PATH="$HOME/.local/node/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
node -v && npm -v
```

## 5. Set up the storefront

```bash
cd ~/Queneth/frontend
cp .env.example .env
npm install
npx next telemetry disable
```

## 6. Start, check and stop

From `~/Queneth`:

| Command | What it does |
| --- | --- |
| `vm/start.sh --prod` | **For the demo.** Checks the setup, starts the API, builds and starts the production storefront, warms the main pages. About 2 minutes. |
| `vm/start.sh` | Development mode (hot reload, Next.js dev overlay). Starts in about 20 s. |
| `vm/status.sh` | Health of both services, VM resources, and a log check. |
| `vm/stop.sh` | Stops both services. |

The servers run in the background in their own session, so **closing the
terminal does not stop them**. Logs are written to `logs/api.log`,
`logs/web.log` and `logs/build.log`.

Expected output of `vm/start.sh --prod`:

```
Queneth: checking the VM
  ✓ Python 3.14.4, Node v22.x, store database present
Starting the API…
  ✓ API ready on http://localhost:8000 (docs at /docs)
Building the storefront for production (about 1–2 minutes)…
  ✓ Build finished
Starting the storefront (production)…
  ✓ Storefront ready on http://localhost:3000
  ✓ Main pages warmed up
```

## 7. Verify before presenting

1. `vm/status.sh` shows **API up**, **Storefront up**, and both logs **clean** (no tracebacks).
2. http://localhost:8000/api/v1/health returns `{"status":"ok", … "database":"ok"}`.
3. http://localhost:8000/docs opens the API's Swagger page.
4. http://localhost:3000 shows the storefront with 31 pieces.
5. Sign in as `admin@queneth.test`; the Control Room loads.

| Account | Role | Password |
| --- | --- | --- |
| `admin@queneth.test` | Admin (Control Room) | `Queneth#2026` |
| `nike@` · `bench@` · `penshoppe@queneth.test` | Seller + buyer | `Queneth#2026` |

QueWallet PIN for every shopper: `123456`. Each wallet starts with QC 50,000.

## 8. Live walkthrough (tested end to end)

1. As **nike@**: open Bench's *Pique Polo*, choose size and color, **Add to Bag**.
2. **Bag → Checkout with QueWallet**: add an address (Region → Province → City → Barangay come from the bundled PSGC list), review, enter PIN `123456`, **Pay**. The order shows *Held in escrow*.
3. Sign out, sign in as **bench@** → **Seller Studio → Orders**: *Start preparing* → *Ship with tracking* → *Mark shipped* → *Mark delivered*.
4. Sign back in as **nike@** → **Account → Orders** → the order → **I received it**. Escrow is released to Bench (minus 5%) and the buyer earns Que Points.
5. As **admin@**: **Control Room → QueWallet → Run reconciliation** reports zero drift; **Integrations → Sent emails** shows the order emails (mock mode).

To reset the store after rehearsing: `vm/stop.sh && cd backend && .venv/bin/python scripts/snapshot.py load --force && cd .. && vm/start.sh --prod`.

## 9. Optional: open the site from the host's browser

The API listens on `127.0.0.1` only, so by default the site works in the VM's
own browser. To use the host's browser, set the VM's address (find it with
`hostname -I`, for example `192.168.56.10`) **before** loading the snapshot:

- `backend/.env`: `API_PUBLIC_URL=http://192.168.56.10:8000`, `FRONTEND_URL=http://192.168.56.10:3000`, `FRONTEND_ORIGINS=http://192.168.56.10:3000`
- `frontend/.env`: `NEXT_PUBLIC_API_URL=http://192.168.56.10:8000/api/v1`, `NEXT_PUBLIC_SITE_URL=http://192.168.56.10:3000`
- run the API with `--public` (edit the `run_demo.py` line in `vm/start.sh`), and if `ufw` is on: `sudo ufw allow 3000,8000/tcp`.

## 10. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Port 8000 (or 3000) is taken` | `vm/stop.sh`, then start again. `ss -ltnp 'sport = :8000'` shows what holds it. |
| `Python environment missing` / `packages missing` | Repeat [step 3](#3-get-the-code-and-set-up-the-back-end). |
| `Node.js missing` | Repeat [step 4](#4-nodejs-22-lts-once-no-root-needed), then open a new terminal. |
| `No store database` | `cd backend && .venv/bin/python scripts/snapshot.py load` |
| A service stops | `vm/status.sh` shows which; `logs/api.log` or `logs/web.log` has the reason; `vm/start.sh` restarts only what is down. |
| First page load is slow | Normal on 2 vCPU; `vm/start.sh` pre-loads the main pages. Give the VM 4 vCPU / 8 GB. |
| Browser console shows `401 (Unauthorized)` for `/api/v1/me` while signed out | Expected: it is the "am I signed in?" check. Nothing is broken. |
| `You have Reduced Motion enabled` | Firefox in a VM reports reduced motion, so animations are toned down. To see them: `about:config` → `ui.prefersReducedMotion` = `0`. |

## 11. Keeping the store in sync with another computer

The store lives in `backend/demo.db` and `backend/uploads/` (not in Git).
`scripts/snapshot.py` packs them into `backend/snapshot/`, which is in Git:

```bash
cd ~/Queneth/backend && .venv/bin/python scripts/snapshot.py save   # after changes in the app
cd ~/Queneth && git add backend/snapshot && git commit -m "Update store snapshot" && git push
```

On the other machine: `git pull`, then `snapshot.py load --force` and restart.
