"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Gift,
  Landmark,
  ReceiptText,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import { DialogTitle, Sheet, SheetContent } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { api, toApiError } from "@/lib/api/client";
import { chunkReference, formatNumber, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useWalletHistory, type LedgerLine, type WalletCategory } from "@/lib/wallet";

const FILTERS: { value: WalletCategory | null; label: string }[] = [
  { value: null, label: "All" },
  { value: "payments", label: "Payments" },
  { value: "refunds", label: "Refunds" },
  { value: "topups", label: "Top-ups" },
  { value: "earnings", label: "Earnings" },
];

const TYPE_META: Record<string, { label: string; icon: LucideIcon }> = {
  GRANT: { label: "Credits granted", icon: Gift },
  TOPUP: { label: "Top-up", icon: Sparkles },
  VOUCHER_REDEEM: { label: "Code redeemed", icon: Gift },
  PAYMENT: { label: "Payment", icon: ArrowUpRight },
  ESCROW_RELEASE: { label: "Earnings released", icon: ArrowDownLeft },
  COMMISSION: { label: "Commission", icon: ReceiptText },
  REFUND: { label: "Refund", icon: RotateCcw },
  WITHDRAWAL: { label: "Payout", icon: Landmark },
  REVERSAL: { label: "Reversal", icon: RotateCcw },
};

/** UX: Miller's Law — references shown in readable chunks: QW-2026-1113-482107. */
export const walletRef = (ref: string) => chunkReference(ref, [2, 4, 4, 6]);

function Amount({ qc, className }: { qc: number; className?: string }) {
  const credit = qc > 0;
  return (
    <span className={cn("tabular font-semibold", credit ? "text-success" : "text-ink", className)}>
      <span className="sr-only">{credit ? "Credit" : "Debit"} </span>
      {credit ? "+" : "−"}QC {formatNumber(Math.abs(qc))}
    </span>
  );
}

export function WalletHistory() {
  const [category, setCategory] = useState<WalletCategory | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const history = useWalletHistory(category);
  const rows = history.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <section aria-labelledby="history-title" className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="history-title" className="text-h2 text-ink">History</h2>
        <a
          href={`${process.env.NEXT_PUBLIC_API_URL}/wallet/statement.csv`}
          className="inline-flex min-h-11 items-center gap-1.5 text-small font-semibold text-accent-2 hover:underline"
          download
        >
          <ReceiptText aria-hidden className="size-4" /> Download statement (CSV)
        </a>
      </div>
      <div role="group" aria-label="Filter history" className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <Chip key={f.label} selected={category === f.value} onClick={() => setCategory(f.value)}>
            {f.label}
          </Chip>
        ))}
      </div>

      {history.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading history">
          {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-20 rounded-card" />)}
        </div>
      ) : history.isError ? (
        <ErrorState message={toApiError(history.error).message} onRetry={() => history.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState icon={ReceiptText} title="Nothing here yet" description={category ? "No transactions of this kind so far." : "Your payments, refunds and top-ups will appear here."} />
      ) : (
        // UX: Common Region — each transaction in its own bounded row.
        <Card className="divide-y divide-border">
          <ul className="divide-y divide-border">
            {rows.map((r) => (
              <li key={r.transaction_id}>
                <Row line={r} onOpen={() => setOpenId(r.transaction_id)} />
              </li>
            ))}
          </ul>
        </Card>
      )}
      {history.hasNextPage && (
        <Button variant="outline" onClick={() => history.fetchNextPage()} loading={history.isFetchingNextPage} className="self-center">
          Older transactions
        </Button>
      )}
      <TransactionSheet id={openId} onClose={() => setOpenId(null)} />
    </section>
  );
}

function Row({ line, onOpen }: { line: LedgerLine; onOpen: () => void }) {
  const meta = TYPE_META[line.type] ?? { label: line.type, icon: ReceiptText };
  const Icon = meta.icon;
  return (
    <button type="button" onClick={onOpen} className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-surface-muted">
      <span className="grid size-11 shrink-0 place-items-center rounded-full bg-surface-muted text-ink">
        <Icon aria-hidden className="size-5" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate font-semibold text-ink">{line.memo ?? meta.label}</span>
        <span className="truncate text-caption text-ink-muted">
          {meta.label} · <span className="tabular">{walletRef(line.reference)}</span> · <time dateTime={line.created_at}>{formatRelative(line.created_at)}</time>
        </span>
      </span>
      <span className="flex flex-col items-end">
        <Amount qc={line.amount_qc} />
        <span className="tabular text-caption text-ink-muted">Balance QC {formatNumber(line.balance_after_qc)}</span>
      </span>
    </button>
  );
}

/** Detail drawer: every ledger entry of the transaction (spec §8). */
function TransactionSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ["wallet", "tx", id],
    enabled: !!id,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/wallet/transactions/{tx_id}", { params: { path: { tx_id: id! } } });
      if (error || !data) throw error;
      return data;
    },
  });
  const d = detail.data;
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" aria-describedby={undefined}>
        <DialogTitle>{d ? TYPE_META[d.type]?.label ?? d.type : "Transaction"}</DialogTitle>
        {detail.isPending ? (
          <Skeleton className="h-64 w-full rounded-card" />
        ) : detail.isError ? (
          <ErrorState message={toApiError(detail.error).message} />
        ) : d ? (
          <div className="flex flex-col gap-6">
            <dl className="grid grid-cols-[120px_1fr] gap-x-4 gap-y-2 text-small">
              <dt className="text-ink-muted">Reference</dt>
              <dd className="tabular font-semibold">{walletRef(d.reference)}</dd>
              <dt className="text-ink-muted">Date</dt>
              <dd>{new Date(d.created_at).toLocaleString("en-PH", { dateStyle: "medium", timeStyle: "short" })}</dd>
              {d.memo && (<><dt className="text-ink-muted">Note</dt><dd>{d.memo}</dd></>)}
              {d.reversed_by && (<><dt className="text-ink-muted">Reversed by</dt><dd className="tabular">{walletRef(d.reversed_by)}</dd></>)}
              {d.reverses && (<><dt className="text-ink-muted">Reverses</dt><dd className="tabular">{walletRef(d.reverses)}</dd></>)}
            </dl>
            <div>
              <h3 className="mb-3 font-sans text-small font-bold uppercase tracking-[0.1em] text-ink-muted">Ledger entries</h3>
              <ul className="flex flex-col divide-y divide-border rounded-card border border-border">
                {d.entries.map((e, i) => (
                  <li key={i} className={cn("flex items-center justify-between gap-3 px-4 py-3", e.is_you && "bg-surface-muted")}>
                    <span className="text-small font-semibold text-ink">{e.wallet}</span>
                    <Amount qc={e.amount_qc} className="text-small" />
                  </li>
                ))}
              </ul>
              <p className="mt-3 flex items-start gap-2 text-caption text-ink-muted">
                <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0" />
                Double-entry: these entries always sum to zero, and they are never edited. Corrections appear as new reversal transactions.
              </p>
            </div>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
