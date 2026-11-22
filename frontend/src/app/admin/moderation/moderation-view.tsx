"use client";

import { EyeOff, Flag, RotateCcw, ShieldCheck, Trash2 } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ReasonForm } from "@/components/admin/reason-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { useModerate, useModeration, type FlagGroup } from "@/lib/admin";
import { cn } from "@/lib/utils";

const fmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });
const REASON = { counterfeit: "Counterfeit", offensive: "Offensive", misleading: "Misleading", spam: "Spam", other: "Other" } as Record<string, string>;
const RESOLUTION = { dismissed: "Kept up", taken_down: "Taken down", restored: "Restored" } as Record<string, string>;

/**
 * Reports from shoppers, grouped per product or review.
 * UX: Serial Position — the most-reported items come first.
 * UX: Hick's Law — two clear outcomes (keep it, take it down) plus restore.
 */
export function ModerationView() {
  const [tab, setTab] = useState<"open" | "resolved">("open");
  const q = useModeration(tab);
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Trust &amp; safety</p>
        <h1 className="text-h1 text-ink">Moderation</h1>
      </header>
      <div role="tablist" aria-label="Report status" className="flex gap-2">
        {(["open", "resolved"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={cn("h-11 rounded-pill border px-4 text-small font-semibold capitalize", tab === t ? "border-ink bg-ink text-bg" : "border-border-strong text-ink hover:bg-surface-muted")}>
            {t}
          </button>
        ))}
      </div>
      {q.isPending ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading reports">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-36 rounded-card" />)}</div>
      ) : q.isError ? (
        <ErrorState message={toApiError(q.error).message} onRetry={() => q.refetch()} />
      ) : q.data.length === 0 ? (
        <EmptyState icon={tab === "open" ? ShieldCheck : Flag} title={tab === "open" ? "Nothing to review" : "No resolved reports yet"} description={tab === "open" ? "Shopper reports on products and reviews appear here." : "Decisions you make are kept here."} />
      ) : (
        <ul className="flex flex-col gap-4">{q.data.map((g) => <FlagCard key={`${g.target_type}-${g.target_id}`} g={g} />)}</ul>
      )}
    </div>
  );
}

function FlagCard({ g }: { g: FlagGroup }) {
  const moderate = useModerate();
  const [panel, setPanel] = useState<"down" | null>(null);
  const takenDown = g.content_status === "removed" || g.content_status === "hidden";
  const run = (action: "dismiss" | "remove" | "hide" | "restore", note?: string) =>
    moderate.mutateAsync({ type: g.target_type, id: g.target_id, action, note }).then(() => {
      toast.success({ dismiss: "Kept up; reports closed", remove: "Taken down", hide: "Review hidden", restore: "Restored" }[action]);
      setPanel(null);
    });

  return (
    <li>
      <Card className="flex flex-col gap-4 p-5">
        <div className="flex flex-wrap items-start gap-4">
          {g.image && <div className="relative aspect-[4/5] w-16 shrink-0 overflow-clip rounded-input bg-surface-muted"><Image src={g.image} alt="" fill sizes="64px" className="object-cover" /></div>}
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="neutral" withIcon={false}>{g.target_type}</Badge>
              {g.url ? <Link href={g.url} target="_blank" className="font-semibold text-ink hover:underline">{g.title}</Link> : <span className="font-semibold text-ink">{g.title}</span>}
              {takenDown && <Badge tone="danger" withIcon={false}>{g.content_status === "hidden" ? "hidden" : "taken down"}</Badge>}
              {g.resolution && g.status === "resolved" && <Badge tone="info" withIcon={false}>{RESOLUTION[g.resolution] ?? g.resolution}</Badge>}
            </div>
            <span className="text-small text-ink-muted">{g.subtitle}</span>
            {g.excerpt && <p className="line-clamp-3 text-small text-ink">{g.excerpt}</p>}
          </div>
          <div className="flex flex-col items-end gap-1 text-right">
            <span className="tabular text-h3 font-bold text-ink">{g.reports}</span>
            <span className="text-caption text-ink-muted">{g.reports === 1 ? "report" : "reports"}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(g.reasons).map(([r, n]) => <Badge key={r} tone="warning" withIcon={false}>{REASON[r] ?? r} × {n}</Badge>)}
          <span className="text-caption text-ink-muted">First {fmt.format(new Date(g.first_reported_at))} · last {fmt.format(new Date(g.last_reported_at))}</span>
        </div>
        {g.notes.length > 0 && (
          <ul className="flex flex-col gap-1 rounded-input bg-surface-muted p-3 text-small text-ink-muted">
            {g.notes.map((n, i) => <li key={i}>“{n}”</li>)}
          </ul>
        )}
        {panel === "down" ? (
          <ReasonForm
            label={g.target_type === "product" ? "Note for the boutique (why it was taken down)" : "Note for the reviewer"}
            confirmLabel={g.target_type === "product" ? "Take down" : "Hide review"}
            danger
            optional
            onSubmit={(note) => run(g.target_type === "product" ? "remove" : "hide", note)}
            onCancel={() => setPanel(null)}
          />
        ) : (
          <div className="flex flex-wrap gap-2">
            {g.status === "open" && !takenDown && (
              <>
                <Button size="sm" variant="outline" loading={moderate.isPending} onClick={() => run("dismiss").catch((e) => toast.error(toApiError(e).message))}>
                  <ShieldCheck aria-hidden /> Keep it up
                </Button>
                <Button size="sm" variant="danger" onClick={() => setPanel("down")}>
                  {g.target_type === "product" ? <Trash2 aria-hidden /> : <EyeOff aria-hidden />} {g.target_type === "product" ? "Take down…" : "Hide review…"}
                </Button>
              </>
            )}
            {takenDown && (
              <Button size="sm" variant="outline" loading={moderate.isPending} onClick={() => run("restore").catch((e) => toast.error(toApiError(e).message))}>
                <RotateCcw aria-hidden /> Restore
              </Button>
            )}
          </div>
        )}
      </Card>
    </li>
  );
}
