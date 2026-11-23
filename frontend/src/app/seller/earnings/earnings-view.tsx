"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Banknote, Lock, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, ErrorState } from "@/components/ui/states";
import { PinInput } from "@/components/wallet/pin-input";
import { toApiError } from "@/lib/api/client";
import { chunkReference, formatQc } from "@/lib/format";
import { useEarnings } from "@/lib/studio";
import { newKey, useWithdraw } from "@/lib/wallet";

const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });

/**
 * Earnings: available vs still in escrow, and a simulated withdrawal.
 * UX: Common Region — what you can move now is separated from what's on hold.
 */
export function EarningsView() {
  const earnings = useEarnings();
  if (earnings.isPending) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading earnings">
        <Skeleton className="h-10 w-60" />
        <div className="grid gap-4 sm:grid-cols-2">{Array.from({ length: 2 }, (_, i) => <Skeleton key={i} className="h-36 rounded-card" />)}</div>
      </div>
    );
  }
  if (earnings.isError) return <ErrorState message={toApiError(earnings.error).message} onRetry={() => earnings.refetch()} />;
  const e = earnings.data;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Earnings</p>
        <h1 className="text-h1 text-ink">Earnings</h1>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="flex flex-col gap-2 p-6">
          <span className="text-small text-ink-muted">Available to withdraw</span>
          <span className="tabular text-h1 font-bold text-ink">{formatQc(e.available_qc)}</span>
          <span className="text-caption text-ink-muted">Your QueWallet balance, including any shopping credit.</span>
        </Card>
        <Card className="flex flex-col gap-2 p-6">
          <span className="flex items-center gap-1.5 text-small text-ink-muted"><ShieldCheck aria-hidden className="size-4" /> In escrow</span>
          <span className="tabular text-h1 font-bold text-ink">{formatQc(e.in_escrow_qc)}</span>
          <span className="text-caption text-ink-muted">After 5% commission. Released when buyers confirm delivery, or 7 days after.</span>
        </Card>
      </div>
      <dl className="grid gap-4 text-small sm:grid-cols-3">
        <Stat label="Released to you" value={e.released_qc} />
        <Stat label="Commission paid (5%)" value={e.commission_paid_qc} />
        <Stat label="Withdrawn" value={e.withdrawn_qc} />
      </dl>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <Card className="flex flex-col gap-4 p-6">
          <h2 className="flex items-center gap-2 text-h3 text-ink"><Banknote aria-hidden className="size-5" /> Withdraw</h2>
          {e.has_pin ? <WithdrawForm available={e.available_qc} /> : (
            <Alert tone="info" title="Set a QueWallet PIN first" action={<Button asChild size="sm" variant="outline"><Link href="/account/wallet">Set PIN</Link></Button>}>
              Withdrawals are confirmed with your 6-digit PIN.
            </Alert>
          )}
          <p className="text-caption text-ink-muted">Simulated payout: QC moves to a holding account and never reaches a real bank. QueWallet credits are simulated for academic purposes and have no cash value.</p>
        </Card>
        <Card className="flex flex-col gap-3 p-6">
          <h2 className="text-h3 text-ink">Payout history</h2>
          {e.payouts.length === 0 ? (
            <p className="text-small text-ink-muted">No withdrawals yet.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {e.payouts.map((p) => (
                <li key={p.reference} className="flex items-center justify-between gap-3 py-2.5 text-small">
                  <span className="flex flex-col">
                    <span className="tabular font-semibold text-ink">{chunkReference(p.reference, [2, 4, 4, 6])}</span>
                    <span className="text-caption text-ink-muted">{dateFmt.format(new Date(p.created_at))}</span>
                  </span>
                  <span className="tabular font-semibold">{formatQc(p.amount_qc)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-1 rounded-card border border-border bg-surface p-4">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="tabular text-h3 font-bold text-ink">{formatQc(value)}</dd>
    </div>
  );
}

function WithdrawForm({ available }: { available: number }) {
  const withdraw = useWithdraw();
  const qc = useQueryClient();
  const [amount, setAmount] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const key = useRef(newKey());
  const value = Number(amount.replace(/[^\d]/g, "")) || 0;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (value < 100) return setError("Withdraw at least QC 100.");
    if (value > available) return setError(`You can withdraw up to ${formatQc(available)}.`);
    if (pin.length !== 6) return setError("Enter your 6-digit PIN.");
    try {
      await withdraw.mutateAsync({ amount: value, pin, key: key.current });
      key.current = newKey();
      toast.success(`${formatQc(value)} withdrawn`, { description: "Simulated payout recorded." });
      setAmount("");
      setPin("");
      qc.invalidateQueries({ queryKey: ["studio", "earnings"] });
    } catch (err) {
      const api = toApiError(err);
      if (api.code !== "network_error") key.current = newKey();
      setPin("");
      setError(api.message);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      {/* UX: Postel's Law — "12,500" and "QC 12500" both work. */}
      <Field label="Amount" hint={`Up to ${formatQc(available)}`}>
        <Input inputMode="numeric" value={amount} onChange={(ev) => setAmount(ev.target.value)} placeholder="e.g. 10,000" />
      </Field>
      <div className="flex flex-wrap gap-2">
        {[25, 50, 100].map((pct) => (
          <button key={pct} type="button" onClick={() => setAmount(String(Math.floor((available * pct) / 100)))} className="h-11 rounded-pill border border-border-strong px-4 text-small font-semibold hover:bg-surface-muted">
            {pct === 100 ? "All" : `${pct}%`}
          </button>
        ))}
      </div>
      <PinInput label="QueWallet PIN" value={pin} onChange={setPin} invalid={!!error && pin.length === 0} />
      {error && <p role="alert" className="text-small text-danger">{error}</p>}
      <Button type="submit" variant="wallet" loading={withdraw.isPending} className="self-start">
        <Lock aria-hidden /> Withdraw {value ? formatQc(value) : ""}
      </Button>
    </form>
  );
}
