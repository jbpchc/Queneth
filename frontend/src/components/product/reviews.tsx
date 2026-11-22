"use client";

import { BadgeCheck, MessageSquareQuote, Star } from "lucide-react";
import { useState } from "react";

import { ReportButton } from "@/components/catalog/report-button";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { api, toApiError, type ApiSchemas } from "@/lib/api/client";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

type Review = ApiSchemas["ReviewOut"];
type Summary = ApiSchemas["ReviewSummary"];

export function Stars({ value, size = "sm" }: { value: number; size?: "sm" | "md" }) {
  return (
    <span className="inline-flex items-center gap-0.5" role="img" aria-label={`${value.toFixed(1)} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          aria-hidden
          className={cn(size === "md" ? "size-5" : "size-4", n <= Math.round(value) ? "fill-ink text-ink" : "text-border-strong")}
        />
      ))}
    </span>
  );
}

const FIT_LABEL = { small: "Runs small", true: "True to size", large: "Runs large" } as const;

/**
 * Reviews sit well below the purchase controls (UX: Proximity), with a
 * summary, rating distribution, fit summary and a verified-purchase list.
 */
export function Reviews({ slug, summary, initial }: { slug: string; summary: Summary; initial: Review[] }) {
  const [items, setItems] = useState(initial);
  const [cursor, setCursor] = useState<string | null | undefined>(summary.count > initial.length ? undefined : null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function more() {
    setLoading(true);
    setError(null);
    // First "load more" starts after the server-rendered six.
    let next = cursor;
    if (next === undefined) {
      const first = await api.GET("/api/v1/catalog/products/{slug}/reviews", { params: { path: { slug }, query: { limit: initial.length } } });
      next = first.data?.next_cursor ?? null;
    }
    const { data, error: err } = await api.GET("/api/v1/catalog/products/{slug}/reviews", {
      params: { path: { slug }, query: { limit: 6, ...(next ? { cursor: next } : {}) } },
    });
    setLoading(false);
    if (err || !data) return setError(toApiError(err).message);
    setItems((prev) => [...prev, ...data.items.filter((r) => !prev.some((p) => p.id === r.id))]);
    setCursor(data.next_cursor);
  }

  return (
    <section aria-labelledby="reviews-title" className="grid gap-10 md:grid-cols-[320px_1fr]">
      <div className="flex flex-col gap-5">
        <h2 id="reviews-title" className="text-h2 text-ink">Reviews</h2>
        {summary.count > 0 && (
          <>
            <div className="flex items-end gap-3">
              <span className="tabular font-display text-display leading-none text-ink">{summary.average.toFixed(1)}</span>
              <div className="flex flex-col gap-1 pb-2">
                <Stars value={summary.average} size="md" />
                <span className="text-small text-ink-muted">{summary.count} verified {summary.count === 1 ? "review" : "reviews"}</span>
              </div>
            </div>
            <ul className="flex flex-col gap-1.5">
              {Object.entries(summary.distribution).map(([stars, n]) => (
                <li key={stars} className="flex items-center gap-3 text-small">
                  <span className="tabular w-8 text-ink-muted">{stars} ★</span>
                  <span className="h-2 flex-1 rounded-pill bg-surface-muted">
                    <span className="block h-full rounded-pill bg-ink" style={{ width: `${summary.count ? (n / summary.count) * 100 : 0}%` }} />
                  </span>
                  <span className="tabular w-6 text-right text-ink-muted">{n}</span>
                </li>
              ))}
            </ul>
            {summary.fit && (
              <p className="text-small text-ink-muted">
                Fit: <strong className="text-ink">{summary.fit_verdict === "runs_small" ? "runs small" : summary.fit_verdict === "runs_large" ? "runs large" : "true to size"}</strong>{" "}
                ({summary.fit.true}% say true to size)
              </p>
            )}
          </>
        )}
        <p className="text-caption text-ink-muted">Only buyers who received this piece can review it.</p>
      </div>
      <div className="flex flex-col gap-4">
        {items.length === 0 ? (
          <EmptyState
            icon={MessageSquareQuote}
            title="No reviews yet"
            description="Be the first to tell other connoisseurs how it wears. Reviews open once your order arrives."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {items.map((r) => (
              <li key={r.id} className="flex flex-col gap-2 py-6 first:pt-0">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Stars value={r.rating} />
                  {r.title && <h3 className="font-sans text-body font-semibold text-ink">{r.title}</h3>}
                </div>
                <p className="max-w-measure text-ink">{r.body}</p>
                <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-ink-muted">
                  <span className="font-semibold text-ink">{r.author}</span>
                  {r.verified && (
                    <span className="inline-flex items-center gap-1 text-success"><BadgeCheck aria-hidden className="size-3.5" /> Verified purchase</span>
                  )}
                  {r.variant_label && <span>{r.variant_label}</span>}
                  {r.fit && <span>{FIT_LABEL[r.fit]}</span>}
                  <time dateTime={r.created_at}>{formatRelative(r.created_at)}</time>
                  {r.helpful_count > 0 && <span>{r.helpful_count} found this helpful</span>}
                  <ReportButton type="review" id={r.id} />
                </p>
                {r.seller_reply && (
                  <blockquote className="mt-2 rounded-input border-l-2 border-ink bg-surface-muted px-4 py-3 text-small text-ink">
                    {r.seller_reply}
                  </blockquote>
                )}
              </li>
            ))}
          </ul>
        )}
        {error && <p role="alert" className="text-small text-danger">{error}</p>}
        {cursor !== null && items.length > 0 && (
          <Button variant="outline" onClick={more} loading={loading} className="self-start">
            More reviews
          </Button>
        )}
      </div>
    </section>
  );
}
