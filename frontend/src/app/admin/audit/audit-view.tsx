"use client";

import { ScrollText } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { useAudit } from "@/lib/admin";

const fmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "medium" });
const TARGETS = ["user", "seller_profile", "sub_order", "product", "review", "category", "subcategory", "collection", "ledger_transaction", "topup_code", "email", "integration"];

/** Append-only record of every privileged action. UX: Chunking — one row per action, details on demand. */
export function AuditView() {
  const [action, setAction] = useState("");
  const [targetType, setTargetType] = useState("");
  const log = useAudit({ action, targetType });
  const rows = log.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Accountability</p>
        <h1 className="text-h1 text-ink">Audit log</h1>
      </header>
      <div className="flex flex-wrap gap-3">
        <Input aria-label="Action" placeholder="Action, e.g. seller.suspend" value={action} onChange={(e) => setAction(e.target.value)} className="w-72" />
        <Select aria-label="Target type" value={targetType} onChange={(e) => setTargetType(e.target.value)} className="w-56">
          <option value="">Any target</option>
          {TARGETS.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </Select>
      </div>
      {log.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading audit log">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-14 rounded-input" />)}</div>
      ) : log.isError ? (
        <ErrorState message={toApiError(log.error).message} onRetry={() => log.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState icon={ScrollText} title="No matching entries" description={action || targetType ? "Actions must match exactly, e.g. user.ban." : "Privileged actions will be recorded here."} />
      ) : (
        <Card className="divide-y divide-border">
          {rows.map((r) => (
            <details key={r.id} className="group px-4 py-3 text-small">
              <summary className="flex min-h-11 cursor-pointer flex-wrap items-center gap-x-3 gap-y-1">
                <span className="tabular w-44 shrink-0 text-ink-muted">{fmt.format(new Date(r.created_at))}</span>
                <span className="font-semibold text-ink">{r.action}</span>
                <span className="text-ink-muted">{r.target_type.replace(/_/g, " ")} · <span className="tabular">{r.target_id.slice(0, 8)}</span></span>
                <span className="ml-auto text-ink-muted">{r.actor ?? "System"}</span>
              </summary>
              <div className="mt-2 flex flex-col gap-1 rounded-input bg-surface-muted p-3 text-caption">
                {r.reason && <p className="text-ink"><span className="font-semibold">Reason:</span> {r.reason}</p>}
                {r.before && <p className="text-ink-muted"><span className="font-semibold text-ink">Before:</span> <code>{JSON.stringify(r.before)}</code></p>}
                {r.after && <p className="text-ink-muted"><span className="font-semibold text-ink">After:</span> <code>{JSON.stringify(r.after)}</code></p>}
                <p className="text-ink-muted">Target {r.target_id}{r.ip && ` · IP ${r.ip}`}</p>
              </div>
            </details>
          ))}
        </Card>
      )}
      {log.hasNextPage && <Button variant="outline" className="self-center" loading={log.isFetchingNextPage} onClick={() => log.fetchNextPage()}>Show older entries</Button>}
    </div>
  );
}
