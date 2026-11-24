"use client";

import { CheckCircle2, MapPin, PenLine, ShieldCheck, Sparkles, Store, Truck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { ReviewForm } from "@/components/orders/review-form";
import { StatusTimeline } from "@/components/orders/status-timeline";
import { SubOrderActions } from "@/components/orders/sub-order-actions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { addressLine, formatPhone, statusLabel, statusTone, useOrder, type SubOrder } from "@/lib/commerce";
import { formatQc, optionLabel } from "@/lib/format";

const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });

/** One order, split per boutique: progress, actions, reviews, payment, delivery. */
export function OrderDetail({ id }: { id: string }) {
  const order = useOrder(id);

  if (order.isPending) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading order">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 rounded-card" />
      </div>
    );
  }
  if (order.isError) {
    return <ErrorState message={toApiError(order.error).message} onRetry={() => order.refetch()} />;
  }
  const o = order.data;
  const a = o.shipping_address;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-3">
        <nav aria-label="Breadcrumb" className="text-small text-ink-muted">
          <Link href="/account" className="hover:underline">Account</Link> /{" "}
          <Link href="/account/orders" className="hover:underline">Orders</Link> / {o.number}
        </nav>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="tabular text-h1 text-ink">{o.number}</h1>
          <Badge tone={statusTone(o.status)} withIcon={false}>{statusLabel[o.status] ?? o.status}</Badge>
        </div>
        <p className="text-small text-ink-muted">
          Placed {dateFmt.format(new Date(o.created_at))}
          {o.sub_orders.length > 1 && <> · {o.sub_orders.length} boutiques, each shipping separately</>}
        </p>
      </header>

      <div className="grid gap-6 md:grid-cols-[1fr_300px]">
        <div className="flex min-w-0 flex-col gap-6">
          {o.sub_orders.map((s) => <SubOrderCard key={s.id} orderId={o.id} sub={s} />)}
        </div>

        <aside className="flex flex-col gap-4 md:sticky md:top-24 md:self-start">
          <Card className="flex flex-col gap-3 p-5 text-small">
            <h2 className="text-h3 text-ink">Payment</h2>
            <dl className="flex flex-col gap-2">
              <div className="flex justify-between"><dt className="text-ink-muted">Items</dt><dd className="tabular">{formatQc(o.subtotal_qc)}</dd></div>
              {o.discount_qc > 0 && <div className="flex justify-between text-success"><dt>Vouchers</dt><dd className="tabular">−{formatQc(o.discount_qc)}</dd></div>}
              <div className="flex justify-between border-t border-border pt-2 font-bold"><dt>Paid with QueWallet</dt><dd className="tabular">{formatQc(o.total_qc)}</dd></div>
            </dl>
            <p className="flex items-start gap-2 text-caption text-ink-muted">
              <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-success" /> Each boutique is paid from escrow only after you receive its pieces.
            </p>
            {o.points_earned > 0 && (
              <p className="flex items-center gap-2 font-semibold text-ink">
                <Sparkles aria-hidden className="size-4 text-accent" /> +{o.points_earned.toLocaleString()} Que Points earned
              </p>
            )}
            {o.points_pending > 0 && (
              <p className="flex items-center gap-2 text-ink-muted">
                <Sparkles aria-hidden className="size-4" /> +{o.points_pending.toLocaleString()} more when delivered
              </p>
            )}
          </Card>
          <Card className="flex flex-col gap-2 p-5 text-small">
            <h2 className="flex items-center gap-2 text-h3 text-ink"><MapPin aria-hidden className="size-4" /> Delivery</h2>
            <p className="text-ink">{a.recipient}</p>
            <p className="tabular text-ink-muted">{formatPhone(a.phone)}</p>
            <p className="text-ink-muted">{addressLine(a)}</p>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function SubOrderCard({ orderId, sub: s }: { orderId: string; sub: SubOrder }) {
  const [reviewing, setReviewing] = useState<string | null>(null);
  return (
    // UX: Common Region — one card per boutique: its progress, pieces and actions together.
    <Card className="overflow-clip">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-5 py-4 text-small">
        <Store aria-hidden className="size-4 text-ink-muted" />
        <Link href={`/b/${s.boutique.slug}`} className="font-semibold text-ink hover:underline">{s.boutique.name}</Link>
        <span className="tabular text-ink-muted">· {s.number}</span>
        <Badge tone={statusTone(s.status)} withIcon={false} className="ml-auto">{statusLabel[s.status] ?? s.status}</Badge>
      </div>

      <div className="flex flex-col gap-4 border-b border-border px-5 py-5">
        <StatusTimeline sub={s} />
        {s.tracking_no && (
          <p className="flex flex-wrap items-center gap-2 text-small text-ink">
            <Truck aria-hidden className="size-4 text-ink-muted" /> Tracking
            <span className="tabular rounded-pill bg-surface-muted px-2.5 py-0.5 font-semibold tracking-[0.04em]">{s.tracking_no}</span>
            <span className="text-caption text-ink-muted">(simulated courier)</span>
          </p>
        )}
        {s.return_reason && (
          <p className="rounded-input bg-warning-soft/60 p-3 text-small text-ink">
            <span className="font-semibold">Your return reason:</span> {s.return_reason}
          </p>
        )}
        <SubOrderActions orderId={orderId} sub={s} />
      </div>

      <ul className="divide-y divide-border">
        {s.items.map((i) => (
          <li key={i.id} className="flex flex-col gap-4 p-5">
            <div className="flex gap-4">
              <Link href={`/p/${i.product_slug}`} className="relative aspect-[4/5] w-20 shrink-0 overflow-hidden rounded-input bg-surface-muted">
                {i.image && <Image src={i.image} alt={i.title} fill sizes="80px" className="object-cover" />}
              </Link>
              <div className="flex min-w-0 flex-1 flex-col gap-1 text-small">
                <p className="text-caption font-bold uppercase tracking-[0.1em] text-ink-muted">{i.brand}</p>
                <Link href={`/p/${i.product_slug}`} className="font-semibold text-ink hover:underline">{i.title}</Link>
                <p className="text-ink-muted">{optionLabel(i.options)} · Qty {i.qty}</p>
                {i.review_id ? (
                  <p className="mt-1 inline-flex items-center gap-1.5 font-semibold text-success">
                    <CheckCircle2 aria-hidden className="size-4" /> Reviewed — thank you
                  </p>
                ) : (
                  i.can_review && reviewing !== i.id && (
                    <Button variant="outline" size="sm" className="mt-2 self-start" onClick={() => setReviewing(i.id)}>
                      <PenLine aria-hidden /> Write a review
                    </Button>
                  )
                )}
              </div>
              <span className="tabular text-small font-semibold">{formatQc(i.line_total_qc)}</span>
            </div>
            {reviewing === i.id && <ReviewForm orderId={orderId} item={i} onDone={() => setReviewing(null)} />}
          </li>
        ))}
      </ul>
      <dl className="flex flex-col gap-1 border-t border-border px-5 py-3 text-small">
        {s.discount_qc > 0 && (
          <div className="flex justify-between text-success"><dt>Voucher {s.voucher_code}</dt><dd className="tabular">−{formatQc(s.discount_qc)}</dd></div>
        )}
        <div className="flex justify-between font-semibold"><dt>Boutique total</dt><dd className="tabular">{formatQc(s.subtotal_qc)}</dd></div>
      </dl>
    </Card>
  );
}
