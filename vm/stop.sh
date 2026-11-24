#!/usr/bin/env bash
# Stop the Queneth API (port 8000) and storefront (port 3000) started by vm/start.sh,
# or by hand in a terminal.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/.run"

stop_group() { # pidfile, name
  [[ -f "$1" ]] || return 0
  local pid; pid="$(cat "$1")"
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
    echo "Stopped $2"
  fi
  rm -f "$1"
}

stop_port() { # port, name: anything still listening (e.g. started by hand)
  local pids
  pids="$(ss -ltnpH "sport = :$1" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u)"
  [[ -z "$pids" ]] && return 0
  kill -TERM $pids 2>/dev/null && echo "Stopped $2 on port $1"
}

stop_group "$RUN/web.pid" "storefront"
stop_group "$RUN/api.pid" "API"
sleep 1
stop_port 3000 "storefront"
stop_port 8000 "API"
rm -f "$RUN/web.mode"

for i in {1..10}; do
  ss -ltn '( sport = :3000 or sport = :8000 )' 2>/dev/null | grep -q LISTEN || { echo "Queneth is stopped."; exit 0; }
  sleep 1
done
echo "Something is still listening on port 3000 or 8000: ss -ltnp '( sport = :3000 or sport = :8000 )'" >&2
exit 1
