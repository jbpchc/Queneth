"use client";

import { ArrowRight, Flag, Store } from "lucide-react";
import Link from "next/link";

import { RevenueChart } from "@/components/studio/revenue-chart";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { useOverview } from "@/lib/admin";
import { formatNumber, formatQc } from "@/lib/format";

/**
 * Control Room overview.
 * UX: Serial Position — what needs a decision (applications, reports) leads;
 * platform health follows. Every number is computed from real records.
 */
export function OverviewView() {
  const o = useOverview();
  if (o.isPending) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading overview">
        <Skeleton className="h-10 w-72" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28 rounded-card" />)}</div>
        <Skeleton className="h-72 rounded-card" />
      </div>
    );
  }
  if (o.isError) return <ErrorState message={toApiError(o.error).message} onRetry={() => o.refetch()} />;
  const d = o.data;
  const topMax = Math.max(1, ...d.top_categories.map((c) => c.revenue_qc));

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Overview</p>
        <h1 className="text-h1 text-ink">Control Room</h1>
      </header>

      {(d.sellers_pending > 0 || d.open_reports > 0) && (
        <section aria-label="Needs a decision" className="grid gap-4 sm:grid-cols-2">
          {d.sellers_pending > 0 && (
            <Attention href="/admin/sellers?status=pending" icon={<Store aria-hidden className="size-5" />} title={`${d.sellers_pending} boutique ${d.sellers_pending === 1 ? "application" : "applications"}`} sub="Waiting for approval" />
          )}
          {d.open_reports > 0 && (
            <Attention href="/admin/moderation" icon={<Flag aria-hidden className="size-5" />} title={`${d.open_reports} reported ${d.open_reports === 1 ? "item" : "items"}`} sub="Open in moderation" />
          )}
        </section>
      )}

      <section aria-label="Platform totals" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Tile label="GMV (all time)" value={formatQc(d.gmv_qc)} sub={`${formatNumber(d.orders)} orders`} />
        <Tile label="GMV, last 30 days" value={formatQc(d.gmv_30d_qc)} sub={`${formatNumber(d.orders_30d)} orders`} />
        <Tile label="Held in escrow" value={formatQc(d.escrow_qc)} sub={`Platform revenue ${formatQc(d.platform_revenue_qc)}`} />
        <Tile label="People" value={formatNumber(d.users_total)} sub={`${d.active_buyers_30d} bought in 30 days · ${d.sellers_active} boutiques`} />
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Card className="p-5 sm:p-6">
          <RevenueChart series={d.series} title="GMV, last 30 days" />
        </Card>
        <Card className="flex flex-col gap-4 p-5 sm:p-6">
          <h2 className="text-small font-semibold text-ink">Top categories <span className="font-normal text-ink-muted">· all time</span></h2>
          {d.top_categories.length === 0 ? (
            <p className="text-small text-ink-muted">Sales by category appear after the first orders.</p>
          ) : (
            <ol className="flex flex-col gap-3">
              {d.top_categories.map((c) => (
                <li key={c.slug} className="flex flex-col gap-1">
                  <div className="flex items-baseline justify-between text-small">
                    <span className="text-ink">{c.name}</span>
                    <span className="tabular text-ink">{formatQc(c.revenue_qc)} <span className="text-caption text-ink-muted">· {c.units} sold</span></span>
                  </div>
                  <div className="h-2 rounded-pill bg-surface-muted"><div className="h-2 rounded-pill bg-accent-2" style={{ width: `${(c.revenue_qc / topMax) * 100}%` }} /></div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <Card className="flex flex-col gap-1 p-5">
      <span className="text-small text-ink-muted">{label}</span>
      <span className="tabular text-h2 font-bold text-ink">{value}</span>
      <span className="text-caption text-ink-muted">{sub}</span>
    </Card>
  );
}

function Attention({ href, icon, title, sub }: { href: string; icon: React.ReactNode; title: string; sub: string }) {
  return (
    <Link href={href} className="flex items-center gap-4 rounded-card border border-warning/50 bg-warning-soft/50 p-5 transition-shadow hover:shadow-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-2">
      <span className="grid size-10 place-items-center rounded-full bg-warning text-bg">{icon}</span>
      <span className="flex flex-1 flex-col">
        <span className="font-semibold text-ink">{title}</span>
        <span className="text-small text-ink-muted">{sub}</span>
      </span>
      <ArrowRight aria-hidden className="size-5 text-ink-muted" />
    </Link>
  );
}
