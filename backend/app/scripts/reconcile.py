"""Recompute every wallet balance from its ledger entries and report drift.

python -m app.scripts.reconcile        # exit code 0 = clean, 1 = drift found
"""

import asyncio
import sys

from app.db.session import SessionLocal, engine
from app.services.wallet_service import reconcile


async def main() -> int:
    async with SessionLocal() as session:
        report = await reconcile(session)
    await engine.dispose()
    print(f"Wallets checked:      {report.wallets_checked}")
    print(f"Transactions checked: {report.transactions_checked}")
    print(f"Sum of all balances:  {report.total_balance_qc} QC (must be 0)")
    for d in report.drift:
        print(f"DRIFT  {d.label}: cached {d.cached_qc} vs entries {d.computed_qc}")
    for ref in report.unbalanced_transactions:
        print(f"UNBALANCED  {ref}")
    print("OK: zero drift." if report.ok else "FAILED: see above.")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
