#!/usr/bin/env bash
# Put the store back to the clean demo state (0 orders, 31 products, the demo
# accounts) and start Queneth again in production mode.
#   vm/reset.sh          reset and start for presenting
#   vm/reset.sh --keep   also save a copy of the current store in ~/queneth-backups first
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "--keep" ]]; then
  mkdir -p ~/queneth-backups
  stamp="$(date +%Y%m%d-%H%M)"
  [[ -f backend/demo.db ]] && cp backend/demo.db ~/queneth-backups/demo.db.$stamp
  [[ -d backend/uploads ]] && tar czf ~/queneth-backups/uploads.$stamp.tgz -C backend uploads
  echo "Saved the current store to ~/queneth-backups/ ($stamp)"
fi

vm/stop.sh
(cd backend && .venv/bin/python scripts/snapshot.py load --force >/dev/null)
echo "Store reset to the clean demo snapshot."
exec vm/start.sh --prod
