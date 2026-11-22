"use client";

import confetti from "canvas-confetti";
import { ArrowRight, MapPin, Sparkles, Store } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { addressLine, formatPhone, useOrder } from "@/lib/commerce";
import { formatQc } from "@/lib/format";
import { easeOut } from "@/lib/motion";

// Brand colors: Que Magenta, Electric Cobalt, citrus, lilac, tangerine.
const CONFETTI_COLORS = ["#c8136e", "#2f4bff", "#d7f94a", "#c9b6ff", "#ff7a1a"];

/**
 * The confirmation is the peak of the journey.
 * UX: Peak-End Rule — a one-time burst of brand confetti and a drawn check mark
 * end the purchase on a high; reloading the page doesn't replay it, and it is
 * skipped entirely for people who prefer reduced motion.
 */
export function SuccessView({ id }: { id: string }) {
  const order = useOrder(id);
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!order.data || reduce) return;
    const flag = `qn-confetti-${id}`;
    try {
      if (sessionStorage.getItem(flag)) return;
      sessionStorage.setItem(flag, "1");
    } catch {
      // Storage blocked: still celebrate once for this render.
    }
    const fire = (originX: number, angle: number) =>
      confetti({ particleCount: 70, spread: 70, startVelocity: 48, angle, origin: { x: originX, y: 0.7 }, colors: CONFETTI_COLORS, disableForReducedMotion: true });
    fire(0.15, 60);
    const t = setTimeout(() => fire(0.85, 120), 180);
    return () => clearTimeout(t);
  }, [order.data, reduce, id]);

  if (order.isPending) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col items-center gap-6" aria-busy="true" aria-label="Loading your order">
        <Skeleton className="size-20 rounded-full" />
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-64 w-full rounded-card" />
      </div>
    );
  }
  if (order.isError) {
    return <ErrorState message={toApiError(order.error).message} onRetry={() => order.refetch()} />;
  }

  const o = order.data;
  const addr = o.shipping_address;
  const pieces = o.sub_orders.reduce((n, s) => n + s.items.reduce((m, i) => m + i.qty, 0), 0);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center gap-8 text-center">
      <AnimatedCheck reduce={!!reduce} />
      <div className="flex flex-col gap-3">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Order confirmed</p>
        <h1 className="text-h1 text-ink">Thank you. It&apos;s yours.</h1>
        <p className="text-body text-ink-muted">
          We&apos;ve sent the receipt to your email and inbox. Each boutique will let you know when it ships.
        </p>
      </div>

      <Card className="w-full overflow-clip text-left">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div>
            <p className="text-caption text-ink-muted">Order number</p>
            {/* UX: Miller's Law — the number is short and chunked to read aloud. */}
            <p className="tabular text-h3 font-bold tracking-[0.04em] text-ink">{o.number}</p>
          </div>
          <div className="text-right">
            <p className="text-caption text-ink-muted">Paid with QueWallet</p>
            <p className="tabular text-h3 font-bold text-ink">{formatQc(o.total_qc)}</p>
          </div>
        </div>
        <ul className="divide-y divide-border">
          {o.sub_orders.map((s) => (
            <li key={s.id} className="flex flex-col gap-3 px-5 py-4">
              <div className="flex items-center gap-2 text-small">
                <Store aria-hidden className="size-4 text-ink-muted" />
                <span className="font-semibold text-ink">{s.boutique.name}</span>
                <span className="tabular text-ink-muted">· {s.number}</span>
                <span className="ml-auto rounded-pill bg-accent-2/10 px-2.5 py-0.5 text-caption font-bold text-accent-2">Held in escrow</span>
              </div>
              <div className="flex gap-2 overflow-x-auto">
                {s.items.map((i) => (
                  <div key={`${i.product_slug}-${JSON.stringify(i.options)}`} className="relative aspect-[4/5] w-16 shrink-0 overflow-hidden rounded-input bg-surface-muted" title={`${i.title} × ${i.qty}`}>
                    {i.image && <Image src={i.image} alt={i.title} fill sizes="64px" className="object-cover" />}
                  </div>
                ))}
              </div>
            </li>
          ))}
        </ul>
        <div className="flex flex-col gap-3 border-t border-border bg-surface-muted/50 px-5 py-4 text-small">
          <p className="flex items-start gap-2 text-ink">
            <MapPin aria-hidden className="mt-0.5 size-4 shrink-0 text-ink-muted" />
            <span>
              {addr.recipient} · {formatPhone(addr.phone)}
              <br />
              <span className="text-ink-muted">{addressLine(addr)}</span>
            </span>
          </p>
          <p className="flex items-center gap-2 font-semibold text-ink">
            <Sparkles aria-hidden className="size-4 text-accent" />
            +{o.points_pending.toLocaleString()} Que Points when delivered
          </p>
        </div>
      </Card>

      <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
        <Button asChild variant="secondary" size="lg">
          <Link href={`/account/orders/${o.id}`}>View order ({pieces} {pieces === 1 ? "piece" : "pieces"})</Link>
        </Button>
        <Button asChild variant="outline" size="lg">
          <Link href="/">Keep exploring <ArrowRight aria-hidden /></Link>
        </Button>
      </div>
    </div>
  );
}

function AnimatedCheck({ reduce }: { reduce: boolean }) {
  return (
    <motion.div
      className="grid size-20 place-items-center rounded-full bg-success text-bg shadow-2"
      initial={reduce ? false : { scale: 0.6, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.4, ease: easeOut }}
      role="img"
      aria-label="Payment complete"
    >
      <svg viewBox="0 0 24 24" className="size-10" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <motion.path
          d="M5 12.5l4.5 4.5L19 7.5"
          initial={reduce ? false : { pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.45, delay: 0.25, ease: easeOut }}
        />
      </svg>
    </motion.div>
  );
}
