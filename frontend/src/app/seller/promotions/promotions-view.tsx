"use client";

import { Percent, X } from "lucide-react";
import Image from "next/image";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { formatQc } from "@/lib/format";
import {
  usePromotionEntries,
  useSellerPromotions,
  useStudioProducts,
  type PromotionOut,
  type SellerEntry,
} from "@/lib/studio";
import { cn } from "@/lib/utils";

const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });
const ENTRY = {
  scheduled: { label: "Starts with the sale", tone: "info" },
  live: { label: "On sale", tone: "success" },
  ended: { label: "Ended", tone: "neutral" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
} as const;

/**
 * Platform sales run by Queneth (e.g. an end-of-year sale). Boutiques choose
 * which pieces join and at what discount; prices drop and return on their own.
 */
export function PromotionsView() {
  const data = useSellerPromotions();
  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Promotions</p>
        <h1 className="text-h1 text-ink">Queneth sales</h1>
        <p className="max-w-measure text-small text-ink-muted">
          Join a Queneth-wide sale with any of your published pieces. Prices drop when the sale starts, the
          original price shows struck through, and everything returns to normal when it ends. While a piece is on
          sale its prices are locked.
        </p>
      </header>

      {data.isPending ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading sales">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-24 rounded-card" />
          ))}
        </div>
      ) : data.isError ? (
        <ErrorState message={toApiError(data.error).message} onRetry={() => data.refetch()} />
      ) : (
        <>
          <section aria-labelledby="open-sales" className="flex flex-col gap-3">
            <h2 id="open-sales" className="text-h3 text-ink">
              Open for entries
            </h2>
            {data.data.open.length === 0 ? (
              <EmptyState
                icon={Percent}
                title="No sales open right now"
                description="When Queneth schedules a platform sale it appears here, and you can enter pieces before it starts."
              />
            ) : (
              <ul className="flex flex-col gap-3">
                {data.data.open.map((p) => (
                  <OpenSale key={p.id} promo={p} />
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="your-entries" className="flex flex-col gap-3">
            <h2 id="your-entries" className="text-h3 text-ink">
              Your pieces in sales
            </h2>
            {data.data.entries.length === 0 ? (
              <p className="text-small text-ink-muted">None yet. Enter pieces into an open sale above.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {data.data.entries.map((e) => (
                  <EntryRow key={e.id} e={e} />
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function OpenSale({ promo }: { promo: PromotionOut }) {
  const [open, setOpen] = useState(false);
  return (
    <li>
      <Card className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-h3 text-ink">{promo.title}</span>
              <Badge tone={promo.state === "live" ? "success" : "info"} withIcon={false}>
                {promo.state === "live" ? "Live" : "Upcoming"}
              </Badge>
            </div>
            <span className="text-small text-ink-muted">
              {dateFmt.format(new Date(promo.starts_at))} – {dateFmt.format(new Date(promo.ends_at))} · discounts{" "}
              {promo.min_discount_percent}–{promo.max_discount_percent}% · {promo.product_count} pieces from{" "}
              {promo.seller_count} boutiques
            </span>
            {promo.description && <span className="text-small text-ink">{promo.description}</span>}
          </div>
          {!open && (
            <Button variant="primary" onClick={() => setOpen(true)}>
              Enter pieces
            </Button>
          )}
        </div>
        {open && <EnrollForm promo={promo} onDone={() => setOpen(false)} />}
      </Card>
    </li>
  );
}

function EnrollForm({ promo, onDone }: { promo: PromotionOut; onDone: () => void }) {
  const products = useStudioProducts("active", "");
  const { enroll } = usePromotionEntries();
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [pct, setPct] = useState(String(Math.max(promo.min_discount_percent, Math.min(20, promo.max_discount_percent))));
  const [error, setError] = useState<string | null>(null);
  const n = Number(pct) || 0;
  const inRange = n >= promo.min_discount_percent && n <= promo.max_discount_percent;

  const toggle = (id: string) =>
    setPicked((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await enroll.mutateAsync({ id: promo.id, product_ids: [...picked], discount_percent: n });
      toast.success(`${picked.size} ${picked.size === 1 ? "piece" : "pieces"} entered in ${promo.title}`);
      onDone();
    } catch (err) {
      setError(toApiError(err).message);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4 border-t border-border pt-4">
      {error && <Alert tone="danger">{error}</Alert>}
      <Field
        label="Discount (%)"
        hint={`Between ${promo.min_discount_percent}% and ${promo.max_discount_percent}%. Rounded down to whole QC.`}
        error={pct && !inRange ? "Outside this sale's range." : undefined}
      >
        <Input inputMode="numeric" value={pct} onChange={(e) => setPct(e.target.value.replace(/\D/g, ""))} className="w-32" />
      </Field>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-small font-semibold text-ink">Pieces</legend>
        {products.isPending ? (
          <Skeleton className="h-32 rounded-card" />
        ) : products.isError ? (
          <ErrorState message={toApiError(products.error).message} onRetry={() => products.refetch()} />
        ) : products.data.items.length === 0 ? (
          <p className="text-small text-ink-muted">Publish a piece first; only live pieces can join a sale.</p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2">
            {products.data.items.map((p) => {
              const on = picked.has(p.id);
              return (
                <li key={p.id}>
                  <button
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggle(p.id)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-input border p-2 text-left transition-colors",
                      on ? "border-ink bg-surface-muted" : "border-border hover:bg-surface-muted",
                    )}
                  >
                    <span className="relative size-12 shrink-0 overflow-hidden rounded-input bg-surface-muted">
                      {p.image && <Image src={p.image} alt="" fill sizes="48px" className="object-cover" />}
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-small font-semibold text-ink">{p.title}</span>
                      <span className="tabular text-caption text-ink-muted">
                        {formatQc(p.min_price_qc)}
                        {inRange && <> → {formatQc(Math.max(1, Math.floor((p.min_price_qc * (100 - n)) / 100)))}</>}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </fieldset>
      <div className="flex gap-3">
        <Button type="submit" variant="primary" loading={enroll.isPending} disabled={!picked.size || !inRange}>
          Enter {picked.size || ""} {picked.size === 1 ? "piece" : "pieces"}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function EntryRow({ e }: { e: SellerEntry }) {
  const { withdraw } = usePromotionEntries();
  const s = ENTRY[e.status];
  const active = e.status === "scheduled" || e.status === "live";
  return (
    <li>
      <Card className="flex flex-wrap items-center gap-4 p-3">
        <span className="relative size-14 shrink-0 overflow-hidden rounded-input bg-surface-muted">
          {e.image && <Image src={e.image} alt="" fill sizes="56px" className="object-cover" />}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="truncate text-small font-semibold text-ink">{e.product_title}</span>
          <span className="text-caption text-ink-muted">
            {e.promotion_title} · {e.discount_percent}% off
          </span>
        </div>
        <span className="tabular text-small">
          <s className="text-ink-muted">{formatQc(e.price_qc)}</s>{" "}
          <span className="font-semibold text-ink">{formatQc(e.sale_price_qc)}</span>
        </span>
        <Badge tone={s.tone} withIcon={false}>
          {s.label}
        </Badge>
        {active && (
          <Button
            size="icon"
            variant="ghost"
            aria-label={`Withdraw ${e.product_title} from ${e.promotion_title}`}
            className="text-ink-muted hover:text-danger"
            loading={withdraw.isPending && withdraw.variables === e.id}
            onClick={() =>
              withdraw.mutate(e.id, {
                onSuccess: () => toast.success(`${e.product_title} withdrawn; its price is back`),
                onError: (err) => toast.error(toApiError(err).message),
              })
            }
          >
            <X aria-hidden />
          </Button>
        )}
      </Card>
    </li>
  );
}
