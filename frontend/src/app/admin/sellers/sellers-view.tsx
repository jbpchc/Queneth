"use client";

import { Check, Search, Star, Store } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ReasonForm } from "@/components/admin/reason-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { useAdminSellers, useSellerActions, type AdminSeller, type SellerStatus } from "@/lib/admin";
import { formatNumber, formatQc } from "@/lib/format";
import { cn } from "@/lib/utils";

const TABS: { value: SellerStatus | null; label: string }[] = [
  { value: "pending", label: "Applications" },
  { value: "approved", label: "Approved" },
  { value: "suspended", label: "Suspended" },
  { value: "rejected", label: "Rejected" },
  { value: null, label: "All" },
];
const TONE = { pending: "warning", approved: "success", suspended: "danger", rejected: "neutral" } as const;
const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium" });

/**
 * Seller directory. UX: Serial Position — applications come first because
 * they wait on us. UX: Hick's Law — each card shows only the actions its status allows.
 */
export function SellersView() {
  const router = useRouter();
  const search = useSearchParams();
  const status = (search.get("status") as SellerStatus | null) ?? (search.has("all") ? null : "pending");
  const [q, setQ] = useState("");
  const list = useAdminSellers(status, q);
  const counts = list.data?.counts ?? {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Boutiques</p>
        <h1 className="text-h1 text-ink">Sellers</h1>
      </header>
      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label="Filter by status" className="flex flex-wrap gap-2">
          {TABS.map((t) => {
            const n = t.value ? counts[t.value] ?? 0 : total;
            const active = status === t.value;
            return (
              <button key={t.label} role="tab" aria-selected={active}
                onClick={() => router.replace(t.value ? `/admin/sellers?status=${t.value}` : "/admin/sellers?all", { scroll: false })}
                className={cn("inline-flex h-11 items-center gap-2 rounded-pill border px-4 text-small font-semibold", active ? "border-ink bg-ink text-bg" : "border-border-strong text-ink hover:bg-surface-muted")}>
                {t.label}
                <span className={cn("tabular rounded-pill px-1.5 text-caption", t.value === "pending" && n > 0 && !active ? "bg-warning text-bg" : "opacity-80")}>{n}</span>
              </button>
            );
          })}
        </div>
        <label className="relative ml-auto w-full sm:w-72">
          <span className="sr-only">Search boutiques or owner emails</span>
          <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-muted" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Boutique or owner email" className="pl-9" />
        </label>
      </div>

      {list.isPending ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading boutiques">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-32 rounded-card" />)}</div>
      ) : list.isError ? (
        <ErrorState message={toApiError(list.error).message} onRetry={() => list.refetch()} />
      ) : list.data.items.length === 0 ? (
        <EmptyState icon={Store} title={status === "pending" ? "No applications waiting" : "No boutiques here"} description={q ? "Try another name or email." : status === "pending" ? "New applications appear here for review." : "Nothing matches this filter."} />
      ) : (
        <ul className="flex flex-col gap-3">{list.data.items.map((s) => <SellerCard key={s.id} s={s} />)}</ul>
      )}
    </div>
  );
}

type Panel = "reject" | "suspend" | null;

function SellerCard({ s }: { s: AdminSeller }) {
  const { approve, reject, suspend, reinstate, feature } = useSellerActions();
  const [panel, setPanel] = useState<Panel>(null);
  const done = (msg: string) => () => {
    toast.success(msg);
    setPanel(null);
  };

  return (
    <li>
      <Card className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-start gap-4">
          <span className="relative size-14 shrink-0 overflow-clip rounded-full bg-surface-muted">
            {s.logo_url && <Image src={s.logo_url} alt="" fill sizes="56px" className="object-cover" />}
          </span>
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              {s.status === "approved" ? <Link href={`/b/${s.slug}`} className="font-semibold text-ink hover:underline">{s.boutique_name}</Link> : <span className="font-semibold text-ink">{s.boutique_name}</span>}
              <Badge tone={TONE[s.status]} withIcon={false}>{s.status}</Badge>
              {s.is_featured && <Badge tone="lilac" withIcon={false}>Featured</Badge>}
            </div>
            <span className="text-small text-ink-muted">{s.owner.name} · {s.owner.email}{s.city && ` · ${s.city}`}</span>
            <span className="text-caption text-ink-muted">
              {s.approved_at ? `Selling since ${dateFmt.format(new Date(s.approved_at))}` : `Applied ${dateFmt.format(new Date(s.created_at))}`}
            </span>
          </div>
          {s.status !== "pending" && (
            <dl className="grid grid-cols-3 gap-4 text-right text-small">
              <div><dt className="text-caption text-ink-muted">Pieces</dt><dd className="tabular font-semibold">{formatNumber(s.product_count)}</dd></div>
              <div><dt className="text-caption text-ink-muted">Orders</dt><dd className="tabular font-semibold">{formatNumber(s.orders)}</dd></div>
              <div><dt className="text-caption text-ink-muted">GMV</dt><dd className="tabular font-semibold">{formatQc(s.gmv_qc)}</dd></div>
            </dl>
          )}
        </div>

        {s.status === "pending" && (
          <div className="flex flex-col gap-1 rounded-input bg-surface-muted p-4 text-small">
            {s.tagline && <p className="font-semibold text-ink">{s.tagline}</p>}
            <p className="text-ink-muted">{s.bio}</p>
          </div>
        )}
        {s.rejection_reason && s.status === "rejected" && <p className="text-small text-ink-muted">Rejected: {s.rejection_reason}</p>}

        {panel === "reject" && (
          <ReasonForm label="Why isn't it approved? The applicant sees this." confirmLabel="Reject application" danger
            onSubmit={(reason) => reject.mutateAsync({ id: s.id, reason }).then(done(`${s.boutique_name} rejected`))} onCancel={() => setPanel(null)} />
        )}
        {panel === "suspend" && (
          <ReasonForm label="Why suspend this boutique? The owner sees this." confirmLabel="Suspend boutique" danger
            onSubmit={(reason) => suspend.mutateAsync({ id: s.id, reason }).then(done(`${s.boutique_name} suspended`))} onCancel={() => setPanel(null)} />
        )}

        {panel === null && (
          <div className="flex flex-wrap gap-2">
            {s.status === "pending" && (
              <>
                <Button size="sm" variant="primary" loading={approve.isPending && approve.variables === s.id}
                  onClick={() => approve.mutate(s.id, { onSuccess: done(`${s.boutique_name} approved`), onError: (e) => toast.error(toApiError(e).message) })}>
                  <Check aria-hidden /> Approve
                </Button>
                <Button size="sm" variant="outline" onClick={() => setPanel("reject")}>Reject…</Button>
              </>
            )}
            {s.status === "approved" && (
              <>
                <Button size="sm" variant="outline" loading={feature.isPending && feature.variables?.id === s.id}
                  onClick={() => feature.mutate({ id: s.id, on: !s.is_featured }, { onSuccess: done(s.is_featured ? "Removed from the home page" : "Featured on the home page"), onError: (e) => toast.error(toApiError(e).message) })}>
                  <Star aria-hidden className={s.is_featured ? "fill-current" : ""} /> {s.is_featured ? "Unfeature" : "Feature on home"}
                </Button>
                <Button size="sm" variant="danger" onClick={() => setPanel("suspend")}>Suspend…</Button>
              </>
            )}
            {s.status === "suspended" && (
              <Button size="sm" variant="primary" loading={reinstate.isPending && reinstate.variables === s.id}
                onClick={() => reinstate.mutate(s.id, { onSuccess: done(`${s.boutique_name} reinstated`), onError: (e) => toast.error(toApiError(e).message) })}>
                Reinstate
              </Button>
            )}
          </div>
        )}
      </Card>
    </li>
  );
}
