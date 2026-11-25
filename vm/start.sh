#!/usr/bin/env bash
# Start Queneth inside the VM: the API (port 8000) and the storefront (port 3000).
#
#   vm/start.sh          development mode (hot reload)
#   vm/start.sh --prod   production build: faster pages, no dev overlay (best for demos)
#
# Both servers run in the background, detached from this terminal, so closing
# the terminal does not stop them. Logs go to logs/api.log and logs/web.log.
# Stop them with vm/stop.sh; check them with vm/status.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/.run"
LOGS="$ROOT/logs"
API_URL="http://localhost:8000/api/v1/health"
WEB_URL="http://localhost:3000/"
mkdir -p "$RUN" "$LOGS"
[[ -d "$HOME/.local/node/bin" ]] && export PATH="$HOME/.local/node/bin:$PATH"

MODE=dev
[[ "${1:-}" == "--prod" ]] && MODE=prod

ok() { printf '  \033[32m✓\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }
up() { curl -fsS --max-time 3 -o /dev/null "$1" 2>/dev/null; }
# The API answers AND can read its database (a server started from a folder
# that was since moved or renamed answers, but every catalog call fails).
api_healthy() { curl -fsS --max-time 5 "$API_URL" 2>/dev/null | grep -q '"database":"ok"' \
  && curl -fsS --max-time 10 -o /dev/null "${API_URL%/health}/catalog/boutiques" 2>/dev/null; }
port_busy() { ss -ltn "sport = :$1" 2>/dev/null | grep -q LISTEN; }

# Run a server in its own session (no controlling terminal, so closing the
# terminal can't stop it). The subshell execs setsid, which execs the server,
# so $! is the server's PID and process group; nothing is left holding stdout.
start_bg() { # dir, log, pidfile, command...
  local dir=$1 log=$2 pidfile=$3
  shift 3
  (cd "$dir" && exec setsid "$@") >"$log" 2>&1 </dev/null &
  echo $! >"$pidfile"
}

wait_for() { # url, seconds, name, log
  for ((i = 0; i < $2; i++)); do
    up "$1" && return 0
    sleep 1
  done
  echo; tail -n 20 "$4" >&2
  fail "$3 did not answer within $2 s (last log lines above, full log: $4)"
}

echo "Queneth: checking the VM"
command -v curl >/dev/null || fail "curl is missing: sudo apt install -y curl"
[[ -x "$ROOT/backend/.venv/bin/python" ]] || fail "Python environment missing: see docs/VM-SETUP.md, step 3"
"$ROOT/backend/.venv/bin/python" -c "import fastapi, sqlalchemy, aiosqlite" 2>/dev/null \
  || fail "Python packages missing: cd backend && .venv/bin/python -m pip install -e '.[dev]'"
command -v node >/dev/null || fail "Node.js missing: see docs/VM-SETUP.md, step 4"
[[ -d "$ROOT/frontend/node_modules" ]] || fail "Frontend packages missing: cd frontend && npm install"
[[ -f "$ROOT/backend/.env" ]] || fail "backend/.env missing: cp backend/.env.example backend/.env"
[[ -f "$ROOT/frontend/.env" ]] || fail "frontend/.env missing: cp frontend/.env.example frontend/.env"
[[ -f "$ROOT/backend/demo.db" ]] || fail "No store database: cd backend && .venv/bin/python scripts/snapshot.py load"
ok "Python $("$ROOT/backend/.venv/bin/python" -c 'import platform; print(platform.python_version())'), Node $(node -v), store database present"

# --- API -------------------------------------------------------------------
if up "$API_URL" && ! api_healthy; then
  echo "The API on port 8000 can't read the store database (was the Queneth folder moved?). Restarting it…"
  "$ROOT/vm/stop.sh" >/dev/null 2>&1 || true
fi
if api_healthy; then
  ok "API already running on port 8000"
else
  port_busy 8000 && fail "Port 8000 is taken by another program: run vm/stop.sh, or: ss -ltnp 'sport = :8000'"
  echo "Starting the API…"
  start_bg "$ROOT/backend" "$LOGS/api.log" "$RUN/api.pid" .venv/bin/python scripts/run_demo.py
  wait_for "$API_URL" 60 "API" "$LOGS/api.log"
  ok "API ready on http://localhost:8000 (docs at /docs)"
fi

# --- Storefront --------------------------------------------------------------
if up "$WEB_URL"; then
  ok "Storefront already running on port 3000"
else
  port_busy 3000 && fail "Port 3000 is taken by another program: run vm/stop.sh, or: ss -ltnp 'sport = :3000'"
  export NEXT_TELEMETRY_DISABLED=1
  if [[ $MODE == prod ]]; then
    # The build pre-renders catalog pages from the API, so it must be serving.
    api_healthy || fail "The API isn't serving the catalog, so the build would fail. See logs/api.log, then run vm/stop.sh and vm/start.sh --prod"
    echo "Building the storefront for production (about 1–2 minutes)…"
    (cd "$ROOT/frontend" && npx next build) >"$LOGS/build.log" 2>&1 \
      || { tail -n 30 "$LOGS/build.log" >&2; fail "Build failed (full log: $LOGS/build.log)"; }
    # next.config.ts uses output: "standalone" (as the Dockerfile does), which runs
    # with server.js and needs the static files and public/ copied next to it.
    SA="$ROOT/frontend/.next/standalone"
    rm -rf "$SA/.next/static" "$SA/public"
    cp -r "$ROOT/frontend/.next/static" "$SA/.next/static"
    cp -r "$ROOT/frontend/public" "$SA/public"
    cp "$ROOT/frontend/.env" "$SA/.env"  # server-side settings such as API_INTERNAL_URL
    ok "Build finished"
    echo "Starting the storefront (production)…"
    PORT=3000 HOSTNAME=0.0.0.0 NODE_ENV=production \
      start_bg "$SA" "$LOGS/web.log" "$RUN/web.pid" node server.js
  else
    echo "Starting the storefront (dev)…"
    start_bg "$ROOT/frontend" "$LOGS/web.log" "$RUN/web.pid" npm run dev
  fi
  echo "$MODE" >"$RUN/web.mode"
  wait_for "$WEB_URL" 180 "Storefront" "$LOGS/web.log"
  ok "Storefront ready on http://localhost:3000"
fi

# Warm the main pages so the first click during a demo is instant.
for p in / /c/clothing /c/shoes /boutiques /login; do
  curl -fsS --max-time 120 -o /dev/null "http://localhost:3000$p" || true
done
ok "Main pages warmed up"

cat <<EOF

Queneth is running.  Open http://localhost:3000 in the VM's browser.
  Admin:   admin@queneth.test       Sellers: nike@ / bench@ / penshoppe@queneth.test
  Password for all: Queneth#2026     QueWallet PIN: 123456
  Status:  vm/status.sh              Stop: vm/stop.sh        Logs: logs/
EOF
