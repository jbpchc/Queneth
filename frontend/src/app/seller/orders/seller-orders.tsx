"use client";

import { Check, Inbox, MapPin, PackageCheck, RefreshCw, Truck, Undo2, X } from "lucide-react";
import Image from "next/image";
import { useState } from "react";
import { toast } from "sonner";

import { StatusTimeline } from "@/components/orders/status-timeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import {
  addressLine,
  formatPhone,
  simulatedTracking,
  statusLabel,
  statusTone,
  useSellerMove,
  useSellerOrders,
  type SellerOrder,
  type SubStatus,
} from "@/lib/commerce";
import { formatQc, optionLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

/** UX: Serial Position — the queue reads in the order work happens; returns sit
 * right after "New" because they need a reply. */
const TABS: { status: SubStatus | null; label: string }[] = [
  { status: null, label: "All" },
  { status: "PAID", label: "New" },
  { status: "RETURN_REQUESTED", label: "Returns" },
  { status: "PROCESSING", label: "Preparing" },
  { status: "SHIPPED", label: "Shipped" },
  { status: "DELIVERED", label: "Delivered" },
  { status: "COMPLETED", label: "Completed" },
  { status: "CANCELLED", label: "Cancelled" },
  { status: "REFUNDED", label: "Refunded" },
];

const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });

/**
 * Fulfilment queue. Phase 8 adds the dashboard and bulk tools around it.
 * UX: Hick's Law — each order shows only the moves the state machine allows.
 */
export function SellerOrders() {
  const [tab, setTab] = useState<SubStatus | null>(null);
  const q = useSellerOrders(tab);
  const counts = q.data?.pages[0]?.counts ?? {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Fulfilment</p>
        <h1 className="text-h1 text-ink">Orders</h1>
        <p className="text-body text-ink-muted">
          Buyers&apos; QC waits in escrow and reaches your wallet (minus 5%) once they confirm delivery, or 7 days after.
        </p>
      </header>

      <div className="-mx-4 overflow-x-auto px-4" role="tablist" aria-label="Filter by status">
        <div className="flex gap-2">
          {TABS.map((t) => {
            const n = t.status ? counts[t.status] ?? 0 : total;
            const active = tab === t.status;
            return (
              <button
                key={t.label}
                role="tab"
                aria-selected={active}
                onClick={() => setTab(t.status)}
                className={cn(
                  "inline-flex h-11 shrink-0 items-center gap-2 rounded-pill border px-4 text-small font-semibold",
                  active ? "border-ink bg-ink text-bg" : "border-border-strong text-ink hover:bg-surface-muted",
                )}
              >
                {t.label}
                <span className={cn("tabular rounded-pill px-1.5 text-caption", active ? "bg-bg/20" : "bg-surface-muted", t.status === "RETURN_REQUESTED" && n > 0 && !active && "bg-warning text-bg")}>{n}</span>
              </button>
            );
          })}
        </div>
      </div>

      {q.isPending ? (
        <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading orders">
          {Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-56 rounded-card" />)}
        </div>
      ) : q.isError ? (
        <ErrorState message={toApiError(q.error).message} onRetry={() => q.refetch()} />
      ) : q.data.pages.flatMap((p) => p.items).length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={tab ? `No ${TABS.find((t) => t.status === tab)?.label.toLowerCase()} orders` : "No orders yet"}
          description={tab ? "Nothing waiting here right now." : "When someone buys from your boutique, it lands here to fulfil."}
        />
      ) : (
        <div className="flex flex-col gap-4">
          {q.data.pages.flatMap((p) => p.items).map((o) => <OrderCard key={o.id} order={o} />)}
          {q.hasNextPage && (
            <Button variant="outline" className="self-center" loading={q.isFetchingNextPage} onClick={() => q.fetchNextPage()}>
              Show older orders
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function OrderCard({ order: o }: { order: SellerOrder }) {
  const a = o.shipping_address;
  return (
    <Card className="overflow-clip">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-5 py-4">
        <span className="tabular font-semibold text-ink">{o.number}</span>
        <Badge tone={statusTone(o.status)} withIcon={false}>{statusLabel[o.status] ?? o.status}</Badge>
        <span className="text-caption text-ink-muted">{dateFmt.format(new Date(o.created_at))}</span>
        <span className="ml-auto text-right text-small">
          <span className="tabular font-bold text-ink">{formatQc(o.net_qc)}</span>
          <span className="block text-caption text-ink-muted">after 5% · {formatQc(o.subtotal_qc)} paid</span>
        </span>
      </div>
      <div className="grid gap-5 p-5 md:grid-cols-[1fr_260px]">
        <div className="flex min-w-0 flex-col gap-4">
          <ul className="flex flex-col gap-3">
            {o.items.map((i) => (
              <li key={i.id} className="flex items-center gap-3">
                <div className="relative aspect-[4/5] w-12 shrink-0 overflow-hidden rounded-input bg-surface-muted">
                  {i.image && <Image src={i.image} alt="" fill sizes="48px" className="object-cover" />}
                </div>
                <div className="min-w-0 flex-1 text-small">
                  <p className="truncate font-semibold text-ink">{i.title}</p>
                  <p className="text-ink-muted">{optionLabel(i.options)} · Qty {i.qty}</p>
                </div>
                <span className="tabular text-small">{formatQc(i.line_total_qc)}</span>
              </li>
            ))}
          </ul>
          {o.voucher_code && <p className="text-caption text-ink-muted">Your voucher {o.voucher_code}: −{formatQc(o.discount_qc)}</p>}
          <StatusTimeline sub={o} />
          {o.return_reason && (
            <p className="rounded-input bg-warning-soft/60 p-3 text-small text-ink">
              <span className="font-semibold">Return reason:</span> {o.return_reason}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1 text-small">
            <p className="flex items-center gap-1.5 font-semibold text-ink"><MapPin aria-hidden className="size-4 text-ink-muted" /> Ship to</p>
            <p className="text-ink">{a.recipient} · <span className="tabular">{formatPhone(a.phone)}</span></p>
            <p className="text-ink-muted">{addressLine(a)}</p>
            {o.tracking_no && <p className="mt-1 text-ink"><Truck aria-hidden className="mr-1 inline size-4" /> <span className="tabular font-semibold">{o.tracking_no}</span></p>}
          </div>
          <Actions order={o} />
        </div>
      </div>
    </Card>
  );
}

type Panel = "ship" | "cancel" | "decline" | null;

function Actions({ order: o }: { order: SellerOrder }) {
  const move = useSellerMove();
  const [panel, setPanel] = useState<Panel>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (o.next.length === 0) {
    if (o.status === "DELIVERED" && o.auto_release_at) {
      return <p className="text-small text-ink-muted">Waiting for the buyer. Escrow auto-releases on {dateFmt.format(new Date(o.auto_release_at))}.</p>;
    }
    return null;
  }

  const go = async (to: SubStatus, extra: { note?: string; trackingNo?: string } = {}, done = "Order updated") => {
    setError(null);
    try {
      await move.mutateAsync({ subId: o.id, to, ...extra });
      toast.success(done);
      setPanel(null);
      setText("");
    } catch (err) {
      setError(toApiError(err).message);
    }
  };
  const open = (p: Panel, initial = "") => {
    setPanel(p);
    setText(initial);
    setError(null);
  };
  const busy = move.isPending;

  if (panel === "ship") {
    return (
      <div className="flex flex-col gap-2">
        <label htmlFor={`trk-${o.id}`} className="text-small font-semibold text-ink">Tracking number</label>
        <div className="flex gap-2">
          <Input id={`trk-${o.id}`} value={text} onChange={(e) => setText(e.target.value.toUpperCase())} className="tabular" autoFocus />
          <Button type="button" variant="outline" size="icon" aria-label="Generate a simulated tracking number" onClick={() => setText(simulatedTracking())}>
            <RefreshCw aria-hidden />
          </Button>
        </div>
        <p className="text-caption text-ink-muted">Simulated courier: generate one or type your own.</p>
        {error && <p role="alert" className="text-small text-danger">{error}</p>}
        <div className="flex gap-2">
          <Button variant="primary" loading={busy} disabled={text.trim().length < 6} onClick={() => go("SHIPPED", { trackingNo: text }, "Marked as shipped. The buyer got an email.")}>
            <Truck aria-hidden /> Mark shipped
          </Button>
          <Button variant="ghost" onClick={() => setPanel(null)}>Back</Button>
        </div>
      </div>
    );
  }
  if (panel === "cancel" || panel === "decline") {
    const cancelling = panel === "cancel";
    return (
      <div className="flex flex-col gap-2">
        <label htmlFor={`why-${o.id}`} className="text-small font-semibold text-ink">
          {cancelling ? "Why are you cancelling?" : "Why are you declining the return?"}
        </label>
        <Textarea id={`why-${o.id}`} rows={3} value={text} onChange={(e) => setText(e.target.value.slice(0, 300))} autoFocus />
        <p className="text-caption text-ink-muted">The buyer sees this.{cancelling && " They're refunded in full right away."}</p>
        {error && <p role="alert" className="text-small text-danger">{error}</p>}
        <div className="flex gap-2">
          <Button
            variant="danger"
            loading={busy}
            disabled={!text.trim()}
            onClick={() =>
              cancelling
                ? go("CANCELLED", { note: text }, "Order cancelled and refunded")
                : go("COMPLETED", { note: text }, "Return declined. Escrow released to you.")
            }
          >
            {cancelling ? "Cancel and refund" : "Decline return"}
          </Button>
          <Button variant="ghost" onClick={() => setPanel(null)}>Back</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {o.next.includes("PROCESSING") && (
        <Button variant="primary" loading={busy} onClick={() => go("PROCESSING", {}, "Preparing. The buyer has been told.")}>
          <Check aria-hidden /> Start preparing
        </Button>
      )}
      {o.next.includes("SHIPPED") && (
        <Button variant="primary" onClick={() => open("ship", simulatedTracking())}>
          <Truck aria-hidden /> Ship with tracking
        </Button>
      )}
      {o.next.includes("DELIVERED") && (
        <Button variant="primary" loading={busy} onClick={() => go("DELIVERED", {}, "Marked delivered (simulated)")}>
          <PackageCheck aria-hidden /> Mark delivered
        </Button>
      )}
      {o.next.includes("REFUNDED") && (
        <Button variant="primary" loading={busy} onClick={() => go("REFUNDED", { note: "Return approved." }, "Return approved. Buyer refunded.")}>
          <Undo2 aria-hidden /> Approve return &amp; refund
        </Button>
      )}
      {o.status === "RETURN_REQUESTED" && o.next.includes("COMPLETED") && (
        <Button variant="outline" onClick={() => open("decline")}>Decline return</Button>
      )}
      {o.next.includes("CANCELLED") && (
        <Button variant="ghost" className="text-ink-muted hover:text-danger" onClick={() => open("cancel")}>
          <X aria-hidden /> Cancel order
        </Button>
      )}
      {error && <p role="alert" className="text-small text-danger">{error}</p>}
    </div>
  );
}
