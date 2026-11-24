"use client";

import confetti from "canvas-confetti";
import { AlertTriangle, ArrowRight, CheckCircle2, PackageOpen, PartyPopper, Truck, Undo2, X } from "lucide-react";
import { useReducedMotion } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import { useEffect } from "react";

import { RevenueChart } from "@/components/studio/revenue-chart";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { formatNumber, formatQc, optionLabel } from "@/lib/format";
import { useDashboard, useDismissFirstSale, type Dashboard } from "@/lib/studio";

/**
 * Seller dashboard: what needs doing first (orders, returns, low stock), then
 * how the boutique is doing.
 * UX: Serial Position — action items lead; analytics follow.
 * UX: Selective Attention — only real numbers; nothing invented to look busy.
 */
export function DashboardView() {
  const dash = useDashboard();

  if (dash.isPending) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading dashboard">
        <Skeleton className="h-10 w-80" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28 rounded-card" />)}</div>
        <Skeleton className="h-72 rounded-card" />
      </div>
    );
  }
  if (dash.isError) return <ErrorState message={toApiError(dash.error).message} onRetry={() => dash.refetch()} />;
  const d = dash.data;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Dashboard</p>
          <h1 className="text-h1 text-ink">Hello, {d.boutique}</h1>
          <p className="text-small text-ink-muted">Here&apos;s how your store is doing today.</p>
        </div>
      </header>

      {d.product_count > 0 && <NextSteps d={d} />}

      {d.first_sale && <FirstSale boutique={d.boutique} />}

      {d.product_count === 0 ? (
        <EmptyState
          icon={PackageOpen}
          title="Add your first product"
          description="A short step-by-step form walks you through photos, sizes and colors, and details. Your progress saves as you go."
          action={<Button asChild variant="primary"><Link href="/seller/products/new">Add a product</Link></Button>}
        />
      ) : null}

      <section aria-label="Today" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Tile label="Sales today" value={formatQc(d.today_revenue_qc)} sub={`${d.today_orders} ${d.today_orders === 1 ? "order" : "orders"}`} />
        <Tile label="Orders to ship" value={formatNumber(d.to_fulfil)} sub="Paid, waiting for you" href="/seller/orders" highlight={d.to_fulfil > 0} />
        <Tile label="Open returns" value={formatNumber(d.returns_open)} sub="Waiting for your reply" href="/seller/orders" highlight={d.returns_open > 0} icon={d.returns_open > 0 ? <Undo2 aria-hidden className="size-4" /> : undefined} />
        <Tile label="Last 30 days" value={formatQc(d.revenue_30d_qc)} sub="Before the 5% Queneth fee" />
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Card className="p-5 sm:p-6">
          <RevenueChart series={d.series} />
        </Card>
        <Card className="flex flex-col gap-4 p-5 sm:p-6">
          <h2 className="text-small font-semibold text-ink">Low stock</h2>
          {d.low_stock.length === 0 ? (
            <p className="text-small text-ink-muted">Everything is above its alert level.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {d.low_stock.map((l) => (
                <li key={l.variant_id} className="flex items-center gap-3 py-2 text-small">
                  <AlertTriangle aria-hidden className={l.stock === 0 ? "size-4 text-danger" : "size-4 text-warning"} />
                  <span className="min-w-0 flex-1 truncate text-ink">{l.title} <span className="text-ink-muted">· {optionLabel(l.options)}</span></span>
                  <span className="tabular font-semibold">{l.stock === 0 ? "Sold out" : `${l.stock} left`}</span>
                </li>
              ))}
            </ul>
          )}
          <Link href="/seller/inventory" className="mt-auto inline-flex min-h-11 items-center gap-1 text-small font-semibold text-accent-2 hover:underline">Update stock <ArrowRight aria-hidden className="size-4" /></Link>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="flex flex-col gap-4 p-5 sm:p-6">
          <h2 className="text-small font-semibold text-ink">From views to orders <span className="font-normal text-ink-muted">· all time</span></h2>
          <FunnelBars f={d.funnel} />
        </Card>
        <Card className="flex flex-col gap-4 p-5 sm:p-6">
          <h2 className="text-small font-semibold text-ink">Best sellers <span className="font-normal text-ink-muted">· last 30 days</span></h2>
          {d.top_products.length === 0 ? (
            <p className="text-small text-ink-muted">Your best sellers will show here after your first orders.</p>
          ) : (
            <ol className="flex flex-col gap-3">
              {d.top_products.map((t, i) => (
                <li key={t.id} className="flex items-center gap-3 text-small">
                  <span className="tabular w-4 text-ink-muted">{i + 1}</span>
                  <div className="relative aspect-[4/5] w-10 shrink-0 overflow-clip rounded-input bg-surface-muted">
                    {t.image && <Image src={t.image} alt="" fill sizes="40px" className="object-cover" />}
                  </div>
                  <span className="min-w-0 flex-1 truncate font-semibold text-ink">{t.title}</span>
                  <span className="tabular text-ink-muted">{t.units} sold</span>
                  <span className="tabular w-24 text-right font-semibold">{formatQc(t.revenue_qc)}</span>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  );
}

/** Plain-language to-do list built from the numbers above. */
function NextSteps({ d }: { d: Dashboard }) {
  const soldOut = d.low_stock.filter((l) => l.stock === 0).length;
  const low = d.low_stock.length - soldOut;
  const steps = [
    d.to_fulfil > 0 && { icon: Truck, text: `Ship ${d.to_fulfil} ${d.to_fulfil === 1 ? "order" : "orders"}`, href: "/seller/orders", cta: "Go to orders" },
    d.returns_open > 0 && { icon: Undo2, text: `Reply to ${d.returns_open} return ${d.returns_open === 1 ? "request" : "requests"}`, href: "/seller/orders", cta: "Review returns" },
    soldOut > 0 && { icon: AlertTriangle, text: `${soldOut} ${soldOut === 1 ? "size or color is" : "sizes or colors are"} sold out`, href: "/seller/inventory", cta: "Restock" },
    low > 0 && { icon: AlertTriangle, text: `${low} running low`, href: "/seller/inventory", cta: "Update stock" },
  ].filter(Boolean) as { icon: typeof Truck; text: string; href: string; cta: string }[];
  return (
    <section aria-labelledby="next-steps" className="flex flex-col gap-3">
      <h2 id="next-steps" className="text-h3 text-ink">Needs your attention</h2>
      {steps.length === 0 ? (
        <Card className="flex items-center gap-3 p-4 text-small text-ink">
          <CheckCircle2 aria-hidden className="size-5 text-success" /> You&apos;re all caught up. Nothing to ship or restock.
        </Card>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {steps.map(({ icon: Icon, text, href, cta }) => (
            <li key={text}>
              <Link href={href} className="flex items-center gap-3 rounded-card border border-border bg-surface p-4 transition-shadow hover:shadow-2">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-accent/10 text-accent"><Icon aria-hidden className="size-[18px]" /></span>
                <span className="min-w-0 flex-1 text-small font-semibold text-ink">{text}</span>
                <span className="inline-flex shrink-0 items-center gap-1 text-small font-semibold text-accent-2">{cta} <ArrowRight aria-hidden className="size-4" /></span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Tile({ label, value, sub, href, highlight, icon }: { label: string; value: string; sub: string; href?: string; highlight?: boolean; icon?: React.ReactNode }) {
  const body = (
    <Card className={`flex h-full flex-col gap-1 p-5 ${highlight ? "border-accent-2/60" : ""} ${href ? "transition-shadow hover:shadow-2" : ""}`}>
      <span className="flex items-center gap-1.5 text-small text-ink-muted">{icon}{label}</span>
      <span className="tabular text-h2 font-bold text-ink">{value}</span>
      <span className="text-caption text-ink-muted">{sub}</span>
    </Card>
  );
  return href ? <Link href={href} className="rounded-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-2">{body}</Link> : body;
}

/** Funnel as a single-hue horizontal bar list (magnitude, one series). */
function FunnelBars({ f }: { f: Dashboard["funnel"] }) {
  const steps = [
    { label: "Views", n: f.views },
    { label: "Wishlisted", n: f.wishlists },
    { label: "Added to bag", n: f.bag_adds },
    { label: "Orders", n: f.orders },
  ];
  const top = Math.max(1, steps[0]!.n);
  return (
    <ol className="flex flex-col gap-3" aria-label="Views, then wishlists, bag adds and orders">
      {steps.map((s, i) => {
        const prev = i > 0 ? steps[i - 1]!.n : null;
        const rate = prev ? Math.round((s.n / prev) * 1000) / 10 : null;
        return (
          <li key={s.label} className="flex flex-col gap-1">
            <div className="flex items-baseline justify-between text-small">
              <span className="text-ink">{s.label}</span>
              <span className="tabular text-ink">
                {formatNumber(s.n)}
                {rate !== null && <span className="ml-2 text-caption text-ink-muted">{rate}% of previous</span>}
              </span>
            </div>
            <div className="h-2 rounded-pill bg-surface-muted">
              <div className="h-2 rounded-pill bg-accent-2" style={{ width: `${Math.max(s.n > 0 ? 1.5 : 0, (s.n / top) * 100)}%` }} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}

const COLORS = ["#c8136e", "#2f4bff", "#d7f94a", "#c9b6ff", "#ff7a1a"];

/** UX: Peak-End — "Your first sale" once, brief, skippable, reduced-motion aware. */
function FirstSale({ boutique }: { boutique: string }) {
  const dismiss = useDismissFirstSale();
  const reduce = useReducedMotion();
  useEffect(() => {
    if (reduce) return;
    confetti({ particleCount: 80, spread: 80, origin: { y: 0.3 }, colors: COLORS, disableForReducedMotion: true });
  }, [reduce]);
  return (
    <div role="status" className="flex items-center gap-4 rounded-card border border-accent/30 bg-accent/10 p-5">
      <PartyPopper aria-hidden className="size-8 shrink-0 text-accent" />
      <div className="flex-1">
        <p className="font-display text-h3 text-ink">Your first sale.</p>
        <p className="text-small text-ink-muted">{boutique} is officially open. Prepare the order and ship it with tracking.</p>
      </div>
      <Button asChild variant="secondary" size="sm"><Link href="/seller/orders">See the order</Link></Button>
      <button type="button" onClick={() => dismiss.mutate()} aria-label="Dismiss" className="grid size-11 place-items-center rounded-full text-ink-muted hover:bg-surface hover:text-ink">
        <X aria-hidden className="size-4" />
      </button>
    </div>
  );
}
