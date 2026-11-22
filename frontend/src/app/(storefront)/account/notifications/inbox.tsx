"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Bell, CheckCheck } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { api, toApiError, type ApiSchemas } from "@/lib/api/client";
import { env } from "@/lib/env";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

type Note = ApiSchemas["NotificationOut"];
const KEY = ["notifications"] as const;

/** Links to our own site become client-side routes; anything else stays external. */
function internalPath(url: string): string | null {
  try {
    const u = new URL(url, env.siteUrl || "http://localhost");
    if (!env.siteUrl || u.origin === new URL(env.siteUrl).origin) return `${u.pathname}${u.search}`;
  } catch {
    /* ignore malformed */
  }
  return null;
}

export function Inbox() {
  const qc = useQueryClient();
  const query = useInfiniteQuery({
    queryKey: KEY,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.GET("/api/v1/notifications", {
        params: { query: pageParam ? { cursor: pageParam } : {} },
      });
      if (error || !data) throw error;
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
  });

  const markRead = useMutation({
    mutationFn: async (id: string) => {
      await api.POST("/api/v1/notifications/{notification_id}/read", {
        params: { path: { notification_id: id } },
      });
    },
    // UX: Doherty Threshold — optimistic: the dot disappears immediately.
    onMutate: (id) => {
      qc.setQueryData(KEY, (old: typeof query.data) =>
        old && {
          ...old,
          pages: old.pages.map((p) => ({
            ...p,
            items: p.items.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)),
          })),
        },
      );
    },
  });
  const markAll = useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/notifications/read-all");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });

  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  const unread = items.some((n) => !n.read_at);

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Your account</p>
          <h1 className="text-h1 text-ink">Inbox</h1>
        </div>
        {unread && (
          <Button variant="ghost" loading={markAll.isPending} onClick={() => markAll.mutate()}>
            <CheckCheck aria-hidden /> Mark all read
          </Button>
        )}
      </header>

      {query.isPending ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading inbox">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-card" />
          ))}
        </div>
      ) : query.isError ? (
        <ErrorState message={toApiError(query.error).message} onRetry={() => query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="All quiet for now"
          description="Order updates, drop alerts and account messages will land here."
          action={
            <Button asChild variant="secondary">
              <Link href="/">Keep exploring</Link>
            </Button>
          }
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((n) => (
            <NoteRow key={n.id} note={n} onRead={() => !n.read_at && markRead.mutate(n.id)} />
          ))}
        </ul>
      )}

      {query.hasNextPage && (
        <Button variant="outline" onClick={() => query.fetchNextPage()} loading={query.isFetchingNextPage}>
          Load older messages
        </Button>
      )}
    </div>
  );
}

function NoteRow({ note, onRead }: { note: Note; onRead: () => void }) {
  const payload = note.payload as { title?: string; body?: string; action_url?: string | null };
  const href = payload.action_url ? internalPath(payload.action_url) : null;
  return (
    <li>
      <Card className={cn("flex gap-4 p-5", !note.read_at && "border-accent-2/40")}>
        <span
          aria-hidden
          className={cn("mt-2 size-2.5 shrink-0 rounded-full", note.read_at ? "bg-transparent" : "bg-accent-2")}
        />
        <div className="flex flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-sans text-body font-semibold text-ink">
              {payload.title ?? "Notification"}
              {!note.read_at && <span className="sr-only"> (unread)</span>}
            </h2>
            <time dateTime={note.created_at} className="text-caption text-ink-muted">
              {formatRelative(note.created_at)}
            </time>
          </div>
          {payload.body && <p className="text-small text-ink-muted">{payload.body}</p>}
          <div className="mt-2 flex flex-wrap gap-2">
            {href && (
              <Button asChild size="sm" variant="secondary" onClick={onRead}>
                <Link href={href}>
                  Open <ArrowRight aria-hidden />
                </Link>
              </Button>
            )}
            {!note.read_at && (
              <Button size="sm" variant="ghost" onClick={onRead}>
                Mark read
              </Button>
            )}
          </div>
        </div>
      </Card>
    </li>
  );
}
