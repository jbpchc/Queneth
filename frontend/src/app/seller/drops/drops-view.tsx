"use client";

import { CalendarClock, Pencil, Plus, Trash2, Users } from "lucide-react";
import Image from "next/image";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { SingleImageField, type GalleryItem } from "@/components/studio/uploads";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { useDropActions, useStudioDrops, useStudioProducts, type StudioDrop } from "@/lib/studio";
import { cn } from "@/lib/utils";

const fmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });
const STATE = { scheduled: { label: "Scheduled", tone: "info" }, live: { label: "Live", tone: "success" }, ended: { label: "Ended", tone: "neutral" } } as const;

/** "2026-11-20T18:00" for <input type="datetime-local"> in the viewer's zone. */
function toLocalInput(iso: string | Date): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Drops: schedule a release; its pieces stay hidden until the start time
 * (real countdowns only). "Notify me" subscribers are told when it goes live.
 */
export function DropsView() {
  const drops = useStudioDrops();
  const [editing, setEditing] = useState<StudioDrop | "new" | null>(null);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Anticipation</p>
          <h1 className="text-h1 text-ink">Product launches</h1>
        </div>
        {editing === null && <Button variant="primary" onClick={() => setEditing("new")}><Plus aria-hidden /> Schedule a drop</Button>}
      </header>

      {editing !== null && <DropForm drop={editing === "new" ? null : editing} onDone={() => setEditing(null)} />}

      {drops.isPending ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading drops">{Array.from({ length: 2 }, (_, i) => <Skeleton key={i} className="h-28 rounded-card" />)}</div>
      ) : drops.isError ? (
        <ErrorState message={toApiError(drops.error).message} onRetry={() => drops.refetch()} />
      ) : drops.data.length === 0 ? (
        editing === null && (
          <EmptyState icon={CalendarClock} title="No drops yet" description="Bundle finished pieces into a release with a real countdown. Shoppers can ask to be notified." action={<Button variant="primary" onClick={() => setEditing("new")}>Schedule a drop</Button>} />
        )
      ) : (
        <ul className="flex flex-col gap-3">
          {drops.data.map((d) => <DropRow key={d.id} d={d} onEdit={() => setEditing(d)} />)}
        </ul>
      )}
    </div>
  );
}

function DropRow({ d, onEdit }: { d: StudioDrop; onEdit: () => void }) {
  const { remove } = useDropActions();
  const s = STATE[d.state];
  return (
    <li>
      <Card className="flex flex-wrap items-center gap-4 p-4">
        <div className="relative aspect-[4/3] w-24 shrink-0 overflow-clip rounded-input bg-surface-muted">
          {d.hero_url && <Image src={d.hero_url} alt="" fill sizes="96px" className="object-cover" />}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-ink">{d.title}</span>
            <Badge tone={s.tone} withIcon={false}>{s.label}</Badge>
          </div>
          <span className="text-small text-ink-muted">{fmt.format(new Date(d.starts_at))}{d.ends_at && ` – ${fmt.format(new Date(d.ends_at))}`}</span>
          <span className="truncate text-small text-ink-muted">{d.products.join(" · ")}</span>
        </div>
        <span className="flex items-center gap-1.5 text-small text-ink-muted"><Users aria-hidden className="size-4" /> {d.subscribers} waiting</span>
        {d.state === "scheduled" && (
          <div className="flex">
            <Button size="icon" variant="ghost" aria-label={`Edit ${d.title}`} onClick={onEdit}><Pencil aria-hidden /></Button>
            <Button size="icon" variant="ghost" aria-label={`Cancel ${d.title}`} className="text-ink-muted hover:text-danger"
              onClick={() => remove.mutate(d.id, { onSuccess: () => toast.success("Drop cancelled", { description: "Pieces that weren't on sale yet are back in your drafts." }), onError: (e) => toast.error(toApiError(e).message) })}>
              <Trash2 aria-hidden />
            </Button>
          </div>
        )}
      </Card>
    </li>
  );
}

function DropForm({ drop, onDone }: { drop: StudioDrop | null; onDone: () => void }) {
  const { save } = useDropActions();
  const products = useStudioProducts(null, "");
  const soon = new Date(Date.now() + 24 * 3600 * 1000);
  soon.setMinutes(0, 0, 0);
  const [title, setTitle] = useState(drop?.title ?? "");
  const [description, setDescription] = useState(drop?.description ?? "");
  const [starts, setStarts] = useState(toLocalInput(drop?.starts_at ?? soon));
  const [ends, setEnds] = useState(drop?.ends_at ? toLocalInput(drop.ends_at) : "");
  const [picked, setPicked] = useState<string[]>(drop?.product_ids ?? []);
  const [hero, setHero] = useState<GalleryItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eligible = (products.data?.items ?? []).filter((p) => p.status !== "archived");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (title.trim().length < 3) return setError("Give the drop a name.");
    if (!picked.length) return setError("Pick at least one piece.");
    try {
      await save.mutateAsync({
        id: drop?.id,
        body: {
          title,
          description: description || null,
          starts_at: new Date(starts).toISOString(),
          ends_at: ends ? new Date(ends).toISOString() : null,
          product_ids: picked,
          hero_asset_id: hero?.assetId ?? null,
        },
      });
      toast.success(drop ? "Drop updated" : "Drop scheduled", { description: "Its pieces stay hidden until it starts." });
      onDone();
    } catch (err) {
      setError(toApiError(err).message);
    }
  };

  return (
    <Card className="p-6">
      <form onSubmit={submit} noValidate className="flex flex-col gap-5">
        <h2 className="text-h3 text-ink">{drop ? `Edit ${drop.title}` : "Schedule a drop"}</h2>
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="grid gap-5 md:grid-cols-[1fr_auto]">
          <div className="flex flex-col gap-5">
            <Field label="Name"><Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} placeholder="Monsoon Edit" /></Field>
            <Field label="Description" optional><Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={1000} /></Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Goes live" hint="Your local time. At least 5 minutes from now."><Input type="datetime-local" value={starts} onChange={(e) => setStarts(e.target.value)} /></Field>
              <Field label="Ends" optional><Input type="datetime-local" value={ends} onChange={(e) => setEnds(e.target.value)} /></Field>
            </div>
          </div>
          <SingleImageField label="Hero image" hint="Defaults to the first piece's photo." purpose="product" url={hero?.url ?? drop?.hero_url ?? null} onUploaded={setHero} />
        </div>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-small font-semibold text-ink">Pieces <span className="font-normal text-ink-muted">· finished drafts or live pieces · {picked.length} picked</span></legend>
          {products.isPending ? <Skeleton className="h-32 rounded-input" /> : eligible.length === 0 ? (
            <p className="text-small text-ink-muted">Create a piece first; finished drafts can launch in a drop.</p>
          ) : (
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
              {eligible.map((p) => {
                const on = picked.includes(p.id);
                return (
                  <li key={p.id}>
                    <button type="button" aria-pressed={on} onClick={() => setPicked((x) => (on ? x.filter((i) => i !== p.id) : [...x, p.id]))}
                      className={cn("flex w-full flex-col gap-1.5 rounded-input border-2 p-1.5 text-left", on ? "border-accent-2" : "border-transparent hover:border-border-strong")}>
                      <span className="relative block aspect-[4/5] overflow-clip rounded-input bg-surface-muted">{p.image && <Image src={p.image} alt="" fill sizes="150px" className="object-cover" />}</span>
                      <span className="line-clamp-1 text-caption font-semibold text-ink">{p.title}</span>
                      <span className="text-caption capitalize text-ink-muted">{p.status === "active" ? "Live" : "Draft"}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="text-caption text-ink-muted">Live pieces you add are hidden until the drop starts, so the countdown is real.</p>
        </fieldset>
        <div className="flex gap-3">
          <Button type="submit" variant="primary" loading={save.isPending}>{drop ? "Save drop" : "Schedule drop"}</Button>
          <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}
