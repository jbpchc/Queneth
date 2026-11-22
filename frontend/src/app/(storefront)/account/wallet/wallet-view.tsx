"use client";

import { KeyRound, Landmark, Lock, Plus, Wallet } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Odometer } from "@/components/wallet/odometer";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { formatQc } from "@/lib/format";
import { useWallet } from "@/lib/wallet";

import { PinDialog, RedeemForm, TopUpDialog, WithdrawDialog } from "./wallet-actions";
import { WalletHistory } from "./wallet-history";

export function WalletView() {
  const { status, hasRole } = useSession();
  const wallet = useWallet();
  const [dialog, setDialog] = useState<"topup" | "pin" | "withdraw" | null>(null);
  // Animate up from 0 on first view, then roll between values (odometer).
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (wallet.data) {
      const t = setTimeout(() => setShown(wallet.data.balance_qc), 60);
      return () => clearTimeout(t);
    }
  }, [wallet.data]);

  const header = (
    <header className="mb-8 flex flex-col gap-2">
      <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Your account</p>
      <h1 className="text-h1 text-ink">QueWallet</h1>
    </header>
  );

  if (status === "guest") {
    return (
      <>
        {header}
        <EmptyState icon={Wallet} title="Sign in to see your wallet" action={<Button asChild variant="primary"><Link href="/login?next=/account/wallet">Sign in</Link></Button>} />
      </>
    );
  }
  if (status === "loading" || wallet.isPending) {
    return (
      <>
        {header}
        <Skeleton className="h-64 rounded-card" aria-label="Loading wallet" />
      </>
    );
  }
  if (wallet.isError) {
    return (<>{header}<ErrorState message={toApiError(wallet.error).message} onRetry={() => wallet.refetch()} /></>);
  }

  const w = wallet.data;
  const seller = hasRole("SELLER");
  return (
    <div className="flex flex-col gap-10">
      {header}
      {!w.has_pin && (
        // UX: Zeigarnik effect — the unfinished setup stays visible.
        <Alert tone="warning" title="Set your QueWallet PIN" action={<Button size="sm" variant="outline" onClick={() => setDialog("pin")}>Set PIN</Button>}>
          You&apos;ll confirm every payment with a 6-digit PIN.
        </Alert>
      )}
      {w.locked_until && (
        <Alert tone="danger" title="Wallet locked">
          Too many wrong PINs. Try again after {new Date(w.locked_until).toLocaleTimeString("en-PH", { hour: "numeric", minute: "2-digit" })}.
        </Alert>
      )}

      <Card className="relative overflow-clip border-0 bg-accent-2 p-0 text-on-accent-2 shadow-3">
        <div aria-hidden className="pointer-events-none absolute -right-20 -top-24 size-80 rounded-full bg-white/10" />
        <div aria-hidden className="pointer-events-none absolute -bottom-32 right-24 size-72 rounded-full bg-white/5" />
        <div className="relative flex flex-col gap-8 p-6 md:p-10">
          <div className="flex items-center justify-between gap-4">
            <span className="inline-flex items-center gap-2 text-small font-semibold">
              <Wallet aria-hidden className="size-5" /> QueWallet
            </span>
            {w.has_pin && (
              <span className="inline-flex items-center gap-1.5 text-caption opacity-80">
                <Lock aria-hidden className="size-3.5" /> PIN protected
              </span>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-small opacity-80">{seller ? "Available" : "Balance"}</span>
            <span className="font-display text-display leading-none">
              <span className="mr-3 align-middle text-h2 font-sans font-semibold opacity-80">QC</span>
              <Odometer value={shown} />
            </span>
            {seller && (
              <span className="tabular mt-2 text-small opacity-80">Pending in escrow: {formatQc(w.pending_qc)}</span>
            )}
          </div>
          <div className="flex flex-wrap gap-3">
            <Button size="lg" onClick={() => setDialog("topup")} className="bg-on-accent-2 text-accent-2 hover:bg-on-accent-2/90">
              <Plus aria-hidden /> Top up
            </Button>
            <Button size="lg" variant="outline" onClick={() => setDialog("pin")} className="border-on-accent-2/40 text-on-accent-2 hover:bg-white/10">
              <KeyRound aria-hidden /> {w.has_pin ? "Change PIN" : "Set PIN"}
            </Button>
            {seller && (
              <Button size="lg" variant="outline" onClick={() => setDialog("withdraw")} disabled={!w.has_pin} className="border-on-accent-2/40 text-on-accent-2 hover:bg-white/10">
                <Landmark aria-hidden /> Withdraw
              </Button>
            )}
          </div>
        </div>
      </Card>

      <Card className="p-6">
        <RedeemForm />
      </Card>

      <WalletHistory />

      <p className="text-caption text-ink-muted">
        QueWallet credits are simulated for academic purposes and have no cash value. 1 QC is shown as a notional PHP 1.
      </p>

      <TopUpDialog wallet={w} open={dialog === "topup"} onOpenChange={(o) => setDialog(o ? "topup" : null)} />
      <PinDialog hasPin={w.has_pin} open={dialog === "pin"} onOpenChange={(o) => setDialog(o ? "pin" : null)} />
      {seller && <WithdrawDialog wallet={w} open={dialog === "withdraw"} onOpenChange={(o) => setDialog(o ? "withdraw" : null)} />}
    </div>
  );
}
