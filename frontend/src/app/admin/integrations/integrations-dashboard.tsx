"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Mail, MapPinned, RefreshCw, RotateCcw, UploadCloud, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Tooltip } from "@/components/ui/tooltip";
import { api, toApiError, type ApiSchemas } from "@/lib/api/client";
import { formatRelative } from "@/lib/format";

type Status = ApiSchemas["IntegrationStatusOut"];
type EmailRow = ApiSchemas["EmailLogOut"];

const icons: Record<Status["name"], LucideIcon> = { psgc: MapPinned, cloudinary: UploadCloud, brevo: Mail };
const healthTone = {
  ok: ["success", "Healthy"],
  degraded: ["danger", "Degraded · fallback active"],
  mock: ["info", "Mock mode"],
  unconfigured: ["warning", "Not configured · fallback active"],
  idle: ["neutral", "No calls yet"],
} as const;
const emailTone = { sent: "success", mocked: "info", queued: "warning", failed: "danger" } as const;

export function IntegrationsDashboard() {
  const qc = useQueryClient();
  const status = useQuery({
    queryKey: ["admin", "integrations"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/integrations");
      if (error || !data) throw error;
      return data;
    },
    refetchInterval: 15_000,
  });
  const check = useMutation({
    mutationFn: async (name: Status["name"]) => {
      const { data, error } = await api.POST("/api/v1/admin/integrations/{name}/check", {
        params: { path: { name } },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: (data) => qc.setQueryData(["admin", "integrations"], data),
    onError: (err) => toast.error("Check failed", { description: toApiError(err).message }),
  });

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Control Room</p>
        <h1 className="text-h1 text-ink">Integrations</h1>
        <p className="max-w-measure text-ink-muted">
          The three external APIs, called only from the Python backend. Each falls back automatically,
          so shoppers never see an outage.
        </p>
      </header>

      <section aria-labelledby="status-title" className="flex flex-col gap-4">
        <h2 id="status-title" className="sr-only">
          API status
        </h2>
        {status.isPending ? (
          <div className="grid gap-4 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-80 rounded-card" />
            ))}
          </div>
        ) : status.isError ? (
          <ErrorState message={toApiError(status.error).message} onRetry={() => status.refetch()} />
        ) : (
          // UX: Common Region — each API in its own bounded panel.
          <div className="grid gap-4 lg:grid-cols-3">
            {status.data.map((s) => (
              <StatusCard
                key={s.name}
                status={s}
                checking={check.isPending && check.variables === s.name}
                onCheck={() => check.mutate(s.name)}
              />
            ))}
          </div>
        )}
      </section>

      <EmailLog />
    </div>
  );
}

function StatusCard({ status: s, checking, onCheck }: { status: Status; checking: boolean; onCheck: () => void }) {
  const Icon = icons[s.name];
  const [tone, label] = healthTone[s.health];
  const rows: [string, string][] = [
    ["Mode", s.mode === "live" ? "Live" : "Mock"],
    ["Last success", s.last_success_at ? formatRelative(s.last_success_at) : "—"],
    ["Last error", s.last_error_at ? `${formatRelative(s.last_error_at)} · ${s.last_error ?? ""}` : "—"],
    ["Latency", s.last_latency_ms != null ? `${s.last_latency_ms} ms` : "—"],
    ["Calls / failures / fallbacks", `${s.calls} / ${s.failures} / ${s.fallbacks}`],
  ];
  const checkButton = (
    <Button variant="outline" size="sm" onClick={onCheck} loading={checking} disabled={s.mode === "mock"}>
      <RefreshCw aria-hidden /> Check now
    </Button>
  );
  return (
    <Card className="flex flex-col">
      <CardHeader className="gap-3">
        <div className="flex items-start justify-between gap-3">
          <span className="grid size-11 place-items-center rounded-full bg-surface-muted text-ink">
            <Icon aria-hidden className="size-5" />
          </span>
          <Badge tone={tone}>{label}</Badge>
        </div>
        <CardTitle>{s.label}</CardTitle>
        <CardDescription>{s.purpose}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <dl className="flex flex-col divide-y divide-border text-small">
          {rows.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-4 py-2">
              <dt className="text-ink-muted">{k}</dt>
              <dd className="tabular text-right text-ink">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="rounded-input bg-surface-muted px-3 py-2 text-caption text-ink-muted">
          <span className="font-semibold text-ink">Fallback:</span> {s.fallback}
        </p>
        <Details name={s.name} details={s.details} />
        <div className="mt-auto">
          {s.mode === "mock" ? (
            <Tooltip content="Set INTEGRATIONS_MODE=live in backend/.env to probe real APIs.">
              <span tabIndex={0} className="inline-flex">
                {checkButton}
              </span>
            </Tooltip>
          ) : (
            checkButton
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Details({ name, details }: { name: Status["name"]; details: Record<string, unknown> }) {
  const d = details as Record<string, never>;
  const items: [string, string][] =
    name === "psgc"
      ? [["Cached lists", String(d.cached_lists)], ["Snapshot", String(d.snapshot_date)]]
      : name === "cloudinary"
        ? [["Cloud", String(d.cloud_name ?? "—")], ["Uploads (cloud / local)", `${d.uploads_cloudinary} / ${d.uploads_local}`]]
        : [
            ["Sender", String(d.sender)],
            [
              "Sent / mocked / queued / failed",
              ((e) => `${e.sent} / ${e.mocked} / ${e.queued} / ${e.failed}`)(d.emails as unknown as Record<string, number>),
            ],
          ];
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-caption">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-ink-muted">{k}</dt>
          <dd className="tabular truncate text-right text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

const FILTERS = [undefined, "sent", "mocked", "queued", "failed"] as const;

function EmailLog() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>(undefined);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const emails = useInfiniteQuery({
    queryKey: ["admin", "emails", filter],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.GET("/api/v1/admin/emails", {
        params: { query: { ...(pageParam ? { cursor: pageParam } : {}), ...(filter ? { status: filter } : {}) } },
      });
      if (error || !data) throw error;
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
  });
  const retry = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await api.POST("/api/v1/admin/emails/{email_id}/retry", {
        params: { path: { email_id: id } },
      });
      if (error) throw error;
    },
    onSuccess: () => {
      toast.success("Email re-queued");
      qc.invalidateQueries({ queryKey: ["admin"] });
    },
  });
  const rows = emails.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <section aria-labelledby="emails-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="emails-title" className="text-h2 text-ink">
            Sent emails
          </h2>
          <p className="text-small text-ink-muted">Every transactional email, newest first.</p>
        </div>
        <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <Chip key={f ?? "all"} selected={filter === f} onClick={() => setFilter(f)}>
              {f ? f[0]!.toUpperCase() + f.slice(1) : "All"}
            </Chip>
          ))}
        </div>
      </div>

      {emails.isPending ? (
        <Skeleton className="h-64 w-full rounded-card" />
      ) : emails.isError ? (
        <ErrorState message={toApiError(emails.error).message} onRetry={() => emails.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState icon={Mail} title="No emails yet" description="Register an account or request a password reset to see one here." />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-small">
            <thead className="border-b border-border text-caption uppercase tracking-[0.08em] text-ink-muted">
              <tr>
                <th scope="col" className="px-5 py-3 font-bold">To</th>
                <th scope="col" className="px-5 py-3 font-bold">Template</th>
                <th scope="col" className="px-5 py-3 font-bold">Status</th>
                <th scope="col" className="px-5 py-3 font-bold">Attempts</th>
                <th scope="col" className="px-5 py-3 font-bold">Created</th>
                <th scope="col" className="px-5 py-3 font-bold"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((e: EmailRow) => (
                <tr key={e.id}>
                  <td className="px-5 py-3 text-ink">{e.to_email}</td>
                  <td className="px-5 py-3"><code className="text-caption">{e.template}</code></td>
                  <td className="px-5 py-3">
                    <Tooltip content={e.last_error ?? e.subject}>
                      <span tabIndex={0}><Badge tone={emailTone[e.status]}>{e.status}</Badge></span>
                    </Tooltip>
                  </td>
                  <td className="tabular px-5 py-3 text-ink">{e.attempts}</td>
                  <td className="px-5 py-3 text-ink-muted">
                    <time dateTime={e.created_at}>{formatRelative(e.created_at)}</time>
                  </td>
                  <td className="px-5 py-3 text-right">
                    {e.status === "mocked" && (
                      <Button size="sm" variant="ghost" onClick={() => setPreviewId(e.id)}>
                        <Eye aria-hidden /> Preview
                      </Button>
                    )}
                    {e.status === "failed" && (
                      <Button size="sm" variant="outline" loading={retry.isPending && retry.variables === e.id} onClick={() => retry.mutate(e.id)}>
                        <RotateCcw aria-hidden /> Retry
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {emails.hasNextPage && (
        <Button variant="outline" onClick={() => emails.fetchNextPage()} loading={emails.isFetchingNextPage}>
          Load more
        </Button>
      )}
      <EmailPreviewDialog id={previewId} onClose={() => setPreviewId(null)} />
    </section>
  );
}

function EmailPreviewDialog({ id, onClose }: { id: string | null; onClose: () => void }) {
  const preview = useQuery({
    queryKey: ["admin", "email-preview", id],
    enabled: !!id,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/admin/emails/{email_id}/preview", {
        params: { path: { email_id: id! } },
      });
      if (error || !data) throw error;
      return data;
    },
  });
  return (
    <Dialog open={!!id} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{preview.data?.subject ?? "Email preview"}</DialogTitle>
          <DialogDescription>Mock mode: this email was not delivered to a real inbox.</DialogDescription>
        </DialogHeader>
        <div className="mt-4">
          {preview.isPending ? (
            <Skeleton className="h-[480px] w-full" />
          ) : preview.isError ? (
            <ErrorState message={toApiError(preview.error).message} />
          ) : (
            // Sandboxed: no scripts, no same-origin access; links open in a new tab.
            <iframe
              title="Email preview"
              sandbox="allow-popups allow-popups-to-escape-sandbox"
              srcDoc={preview.data.html.replace("<html>", '<html><head><base target="_blank"></head>')}
              className="h-[480px] w-full rounded-input border border-border bg-white"
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
