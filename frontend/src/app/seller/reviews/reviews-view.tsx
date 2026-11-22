"use client";

import { MessageSquareQuote, Star } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { useReply, useStudioReviews, type StudioReview } from "@/lib/studio";

const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium" });

/** Reviews of the boutique's pieces, with a public reply. */
export function ReviewsView() {
  const [unreplied, setUnreplied] = useState(true);
  const reviews = useStudioReviews(unreplied);
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Community</p>
          <h1 className="text-h1 text-ink">Reviews</h1>
        </div>
        <label className="flex min-h-11 items-center gap-3 text-small font-semibold text-ink">
          <Switch checked={unreplied} onCheckedChange={(v) => setUnreplied(v === true)} /> Needs a reply
        </label>
      </header>
      {reviews.isPending ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading reviews">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-32 rounded-card" />)}</div>
      ) : reviews.isError ? (
        <ErrorState message={toApiError(reviews.error).message} onRetry={() => reviews.refetch()} />
      ) : reviews.data.length === 0 ? (
        <EmptyState icon={MessageSquareQuote} title={unreplied ? "You're all caught up" : "No reviews yet"} description={unreplied ? "Every review has a reply." : "Verified buyers can review pieces once delivered."} />
      ) : (
        <ul className="flex flex-col gap-4">{reviews.data.map((r) => <ReviewCard key={r.id} r={r} />)}</ul>
      )}
    </div>
  );
}

function ReviewCard({ r }: { r: StudioReview }) {
  const reply = useReply();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(r.seller_reply ?? "");
  return (
    <li>
      <Card className="flex flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center gap-2 text-small">
          <span className="flex" aria-label={`${r.rating} of 5 stars`}>
            {[1, 2, 3, 4, 5].map((i) => <Star key={i} aria-hidden className={i <= r.rating ? "size-4 fill-accent text-accent" : "size-4 text-border-strong"} />)}
          </span>
          <span className="font-semibold text-ink">{r.author}</span>
          <span className="text-ink-muted">· {dateFmt.format(new Date(r.created_at))} · on <Link href={`/p/${r.product_slug}`} className="underline">{r.product_title}</Link></span>
        </div>
        {r.title && <p className="font-semibold text-ink">{r.title}</p>}
        <p className="text-small text-ink">{r.body}</p>
        {r.photos.length > 0 && (
          <div className="flex gap-2">
            {r.photos.map((p) => <div key={p} className="relative size-16 overflow-clip rounded-input bg-surface-muted"><Image src={p} alt="Buyer photo" fill sizes="64px" className="object-cover" /></div>)}
          </div>
        )}
        {r.seller_reply && !open && (
          <div className="rounded-input bg-surface-muted p-3 text-small">
            <p className="font-semibold text-ink">Your reply</p>
            <p className="text-ink-muted">{r.seller_reply}</p>
          </div>
        )}
        {open ? (
          <div className="flex flex-col gap-2">
            <label htmlFor={`reply-${r.id}`} className="text-small font-semibold text-ink">Public reply</label>
            <Textarea id={`reply-${r.id}`} rows={3} value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} autoFocus />
            <div className="flex gap-2">
              <Button variant="primary" size="sm" loading={reply.isPending} disabled={text.trim().length < 2}
                onClick={() => reply.mutate({ id: r.id, reply: text }, {
                  onSuccess: () => { toast.success("Reply posted"); setOpen(false); },
                  onError: (e) => toast.error(toApiError(e).message),
                })}>
                Post reply
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
            </div>
          </div>
        ) : (
          <Button variant="outline" size="sm" className="self-start" onClick={() => setOpen(true)}>{r.seller_reply ? "Edit reply" : "Reply"}</Button>
        )}
      </Card>
    </li>
  );
}
