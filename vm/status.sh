#!/usr/bin/env bash
# Show whether Queneth is up, what the VM has to work with, and any errors in the logs.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS="$ROOT/logs"
green() { printf '\033[32m%s\033[0m' "$*"; }
red() { printf '\033[31m%s\033[0m' "$*"; }

echo "Services"
if health="$(curl -fsS --max-time 3 http://localhost:8000/api/v1/health 2>/dev/null)"; then
  echo "  API         $(green up)    http://localhost:8000   $health"
else
  echo "  API         $(red down)  (start with vm/start.sh)"
fi
if code="$(curl -sS --max-time 30 -o /dev/null -w '%{http_code}' http://localhost:3000/ 2>/dev/null)" && [[ $code == 200 ]]; then
  echo "  Storefront  $(green up)    http://localhost:3000   ($(cat "$ROOT/.run/web.mode" 2>/dev/null || echo started by hand) mode)"
else
  echo "  Storefront  $(red down)  (start with vm/start.sh)"
fi
if [[ -f "$ROOT/backend/demo.db" ]]; then
  echo "  Database    SQLite file backend/demo.db ($(du -h "$ROOT/backend/demo.db" | cut -f1))"
fi

echo
echo "VM resources"
echo "  CPUs        $(nproc)"
free -h | awk '/^Mem:/ {print "  Memory      " $2 " total, " $7 " available"}'
df -h "$ROOT" | awk 'NR==2 {print "  Disk        " $4 " free of " $2}'

echo
echo "Log check (logs/)"
found=0
for f in "$LOGS"/api.log "$LOGS"/web.log; do
  [[ -f "$f" ]] || continue
  hits="$(grep -nE 'Traceback|ERROR|Error:|⨯|Unhandled|EADDRINUSE' "$f" | grep -v 'error_count' | tail -n 5)"
  if [[ -n "$hits" ]]; then
    found=1
    echo "  $(red "$(basename "$f")"):"
    echo "$hits" | sed 's/^/    /'
  else
    echo "  $(basename "$f"): $(green clean)"
  fi
done
[[ $found == 0 ]] || exit 1
