"use client";

import { FastForward, Gift, ReceiptText, ShieldCheck, Ticket, Undo2 } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { ReasonForm } from "@/components/admin/reason-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, EmptyState, ErrorState } from "@/components/ui/states";
import { fieldErrors, toApiError, type ApiSchemas } from "@/lib/api/client";
import { useCodes, useLedger, useSystemWallets, useWalletActions, type AdminTx } from "@/lib/admin";
import { chunkReference, formatQc } from "@/lib/format";
import { newKey } from "@/lib/wallet";
import { cn } from "@/lib/utils";

const fmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });
const TYPES = ["GRANT", "TOPUP", "VOUCHER_REDEEM", "PAYMENT", "ESCROW_RELEASE", "COMMISSION", "REFUND", "WITHDRAWAL", "REVERSAL"];

/**
 * Platform QueWallet tools. UX: Common Region — read-only health (balances,
 * reconciliation) is separated from tools that move money, which all ask for
 * a reason and are audit-logged.
 */
export function WalletAdminView() {
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Ledger</p>
        <h1 className="text-h1 text-ink">QueWallet</h1>
        <p className="text-small text-ink-muted">QueWallet credits are simulated for academic purposes and have no cash value.</p>
      </header>
      <Health />
      <div className="grid gap-6 lg:grid-cols-2">
        <GrantForm />
        <Codes />
      </div>
      <Ledger />
    </div>
  );
}

function Health() {
  const sys = useSystemWallets();
  const { reconcile, fastForward } = useWalletActions();
  const r = reconcile.data;
  return (
    <section aria-label="Platform balances" className="flex flex-col gap-4">
      {sys.isPending ? <Skeleton className="h-28 rounded-card" /> : sys.isError ? <ErrorState message={toApiError(sys.error).message} onRetry={() => sys.refetch()} /> : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {sys.data.map((w) => (
            <Card key={w.code} className="flex flex-col gap-1 p-5">
              <span className="text-small text-ink-muted">{w.label}</span>
              <span className="tabular text-h3 font-bold text-ink">{formatQc(w.balance_qc)}</span>
              <span className="text-caption text-ink-muted">{w.code}</span>
            </Card>
          ))}
        </div>
      )}
      <Card className="flex flex-wrap items-center gap-4 p-5">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="font-semibold text-ink">Reconciliation</span>
          {r ? (
            <span className={cn("text-small", r.ok ? "text-success" : "text-danger")} role="status">
              {r.ok ? "Zero drift." : `${r.drift.length} wallets drifted, ${r.unbalanced_transactions.length} unbalanced transactions.`}{" "}
              <span className="text-ink-muted">{r.wallets_checked} wallets · {r.transactions_checked} transactions · sum {formatQc(r.total_balance_qc)} (must be 0)</span>
            </span>
          ) : (
            <span className="text-small text-ink-muted">Recompute every balance from its ledger entries.</span>
          )}
        </div>
        <Button variant="outline" loading={reconcile.isPending} onClick={() => reconcile.mutate(undefined, { onError: (e) => toast.error(toApiError(e).message) })}>
          <ShieldCheck aria-hidden /> Run reconciliation
        </Button>
        <Button variant="outline" loading={fastForward.isPending}
          onClick={() => fastForward.mutate(undefined, {
            onSuccess: (res) => toast.success(res.released ? `Released escrow for ${res.released} delivered ${res.released === 1 ? "order" : "orders"}` : "Nothing delivered is waiting for release"),
            onError: (e) => toast.error(toApiError(e).message),
          })}>
          <FastForward aria-hidden /> Fast-forward escrow (demo)
        </Button>
      </Card>
      {r && !r.ok && (
        <Alert tone="danger" title="Drift detected">
          {r.drift.map((d) => `${d.label}: cached ${d.cached_qc}, computed ${d.computed_qc}`).join(" · ")}
        </Alert>
      )}
    </section>
  );
}

function GrantForm() {
  const { grant } = useWalletActions();
  const [email, setEmail] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const key = useRef(newKey());
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErrors({});
    try {
      await grant.mutateAsync({ body: { email: email.trim(), amount_qc: Number(amount.replace(/[^\d]/g, "")) || 0, reason }, key: key.current });
      key.current = newKey();
      toast.success(`Granted ${formatQc(Number(amount.replace(/[^\d]/g, "")))} to ${email.trim()}`);
      setEmail(""); setAmount(""); setReason("");
    } catch (err) {
      const api = toApiError(err);
      if (api.code !== "network_error") key.current = newKey();
      const f = fieldErrors(api);
      setErrors(Object.keys(f).length ? f : { form: api.message });
    }
  };
  return (
    <Card className="p-5">
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <h2 className="flex items-center gap-2 text-h3 text-ink"><Gift aria-hidden className="size-5" /> Grant credits</h2>
        {errors.form && <Alert tone="danger">{errors.form}</Alert>}
        <Field label="Recipient email" error={errors.email}><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Amount (QC)" error={errors.amount_qc}><Input inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="5,000" /></Field>
        <Field label="Reason" error={errors.reason} hint="Required; recorded in the ledger memo and audit log."><Input value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} /></Field>
        <Button type="submit" variant="primary" className="self-start" loading={grant.isPending} disabled={!email || !amount || reason.trim().length < 5}>Grant</Button>
      </form>
    </Card>
  );
}

function Codes() {
  const codes = useCodes();
  const { createCode } = useWalletActions();
  const [amount, setAmount] = useState("1000");
  const [uses, setUses] = useState("1");
  const [code, setCode] = useState("");
  const [expires, setExpires] = useState("");
  const [memo, setMemo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const body: ApiSchemas["CodeCreate"] = {
        amount_qc: Number(amount.replace(/[^\d]/g, "")) || 0,
        max_uses: Number(uses) || 1,
        code: code || null,
        memo: memo || null,
        expires_at: expires ? new Date(`${expires}T23:59:59`).toISOString() : null,
      };
      const c = await createCode.mutateAsync(body);
      toast.success(`Code ${c.code} issued`);
      setCode(""); setMemo("");
    } catch (err) {
      setError(toApiError(err).message);
    }
  };
  return (
    <Card className="flex flex-col gap-4 p-5">
      <h2 className="flex items-center gap-2 text-h3 text-ink"><Ticket aria-hidden className="size-5" /> Top-up codes</h2>
      <form onSubmit={submit} noValidate className="grid gap-3 sm:grid-cols-2">
        {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
        <Field label="Amount (QC)"><Input inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
        <Field label="Uses"><Input inputMode="numeric" value={uses} onChange={(e) => setUses(e.target.value.replace(/\D/g, ""))} /></Field>
        <Field label="Code" optional hint="Leave blank to generate."><Input value={code} maxLength={40} onChange={(e) => setCode(e.target.value.toUpperCase())} className="uppercase" /></Field>
        <Field label="Expires" optional><Input type="date" value={expires} onChange={(e) => setExpires(e.target.value)} /></Field>
        <Field label="Memo" optional className="sm:col-span-2"><Input value={memo} maxLength={200} onChange={(e) => setMemo(e.target.value)} /></Field>
        <Button type="submit" variant="primary" className="self-start" loading={createCode.isPending}>Issue code</Button>
      </form>
      {codes.isPending ? <Skeleton className="h-24 rounded-input" /> : codes.isError ? <ErrorState message={toApiError(codes.error).message} onRetry={() => codes.refetch()} /> : codes.data.length === 0 ? (
        <p className="text-small text-ink-muted">No codes yet.</p>
      ) : (
        <ul className="flex max-h-64 flex-col divide-y divide-border overflow-y-auto rounded-input border border-border">
          {codes.data.map((c) => (
            <li key={c.id} className="flex items-center gap-3 px-3 py-2 text-small">
              <span className="tabular font-bold tracking-[0.04em] text-ink">{c.code}</span>
              <span className="tabular text-ink-muted">{formatQc(c.amount_qc)}</span>
              <span className="tabular ml-auto text-ink-muted">{c.used_count}/{c.max_uses} used</span>
              {!c.is_active && <Badge tone="neutral" withIcon={false}>inactive</Badge>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Ledger() {
  const [type, setType] = useState<string | null>(null);
  const ledger = useLedger(type);
  const rows = ledger.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <section className="flex flex-col gap-4" aria-labelledby="ledger-heading">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="ledger-heading" className="flex items-center gap-2 text-h3 text-ink"><ReceiptText aria-hidden className="size-5" /> Ledger</h2>
        <Select aria-label="Transaction type" value={type ?? ""} onChange={(e) => setType(e.target.value || null)} className="ml-auto w-56">
          <option value="">All types</option>
          {TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ").toLowerCase()}</option>)}
        </Select>
      </div>
      {ledger.isPending ? <Skeleton className="h-64 rounded-card" /> : ledger.isError ? <ErrorState message={toApiError(ledger.error).message} onRetry={() => ledger.refetch()} /> : rows.length === 0 ? (
        <EmptyState icon={ReceiptText} title="No transactions" description="Nothing of this type yet." />
      ) : (
        <Card className="divide-y divide-border">
          {rows.map((t) => <TxRow key={t.id} t={t} />)}
        </Card>
      )}
      {ledger.hasNextPage && <Button variant="outline" className="self-center" loading={ledger.isFetchingNextPage} onClick={() => ledger.fetchNextPage()}>Show older</Button>}
    </section>
  );
}

function TxRow({ t }: { t: AdminTx }) {
  const { reverse } = useWalletActions();
  const [reversing, setReversing] = useState(false);
  return (
    <details className="px-4 py-3 text-small">
      <summary className="flex min-h-11 cursor-pointer flex-wrap items-center gap-x-3 gap-y-1">
        <span className="tabular w-40 shrink-0 text-ink-muted">{fmt.format(new Date(t.created_at))}</span>
        <Badge tone={t.type === "REVERSAL" ? "warning" : "neutral"} withIcon={false}>{t.type.replace(/_/g, " ").toLowerCase()}</Badge>
        <span className="min-w-0 flex-1 truncate text-ink">{t.memo}</span>
        {t.reversed && <Badge tone="danger" withIcon={false}>reversed</Badge>}
        <span className="tabular font-semibold text-ink">{formatQc(t.total_qc)}</span>
      </summary>
      <div className="mt-2 flex flex-col gap-2 rounded-input bg-surface-muted p-3">
        <span className="tabular text-caption text-ink-muted">{chunkReference(t.reference, [2, 4, 4, 6])}</span>
        <table className="text-caption">
          <tbody>
            {t.entries.map((e, i) => (
              <tr key={i}>
                <td className="py-0.5 pr-4 text-ink">{e.wallet}</td>
                <td className={cn("tabular py-0.5 text-right", e.amount_qc < 0 ? "text-danger" : "text-success")}>{e.amount_qc > 0 ? "+" : ""}{formatQc(e.amount_qc)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!t.reversed && t.type !== "REVERSAL" && (reversing ? (
          <ReasonForm label="Why reverse it? A new opposite transaction is posted; nothing is edited." confirmLabel="Post reversal" danger
            onSubmit={(reason) => reverse.mutateAsync({ id: t.id, reason }).then(() => { toast.success("Reversal posted"); setReversing(false); })}
            onCancel={() => setReversing(false)} />
        ) : (
          <Button size="sm" variant="outline" className="self-start" onClick={() => setReversing(true)}><Undo2 aria-hidden /> Reverse…</Button>
        ))}
      </div>
    </details>
  );
}
