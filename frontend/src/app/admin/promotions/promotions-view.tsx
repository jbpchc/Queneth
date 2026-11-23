"use client";

import { Ban, Pencil, Percent, Plus } from "lucide-react";
import Link from "next/link";
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
import { fieldErrors, toApiError } from "@/lib/api/client";
import { useAdminPromotions, usePromotionActions, type AdminPromotion } from "@/lib/admin";

const STATE = {
  upcoming: { label: "Upcoming", tone: "info" },
  live: { label: "Live", tone: "success" },
  ended: { label: "Ended", tone: "neutral" },
  cancelled: { label: "Cancelled", tone: "neutral" },
} as const;
const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });

/** `datetime-local` wants local "YYYY-MM-DDTHH:mm". */
function toLocalInput(iso: string) {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Platform-wide sales (e.g. "End of the Year Sale"). Admins set the window and
 * the allowed discount range; boutiques enter their own pieces from the Studio.
 */
export function AdminPromotionsView() {
  const promos = useAdminPromotions();
  const [editing, setEditing] = useState<AdminPromotion | "new" | null>(null);
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Merchandising</p>
          <h1 className="text-h1 text-ink">Promotions</h1>
          <p className="max-w-measure text-small text-ink-muted">
            Boutiques enter pieces at a discount within your range. Sale prices start and end on schedule; cancelling
            restores every price right away.
          </p>
        </div>
        {!editing && (
          <Button variant="primary" onClick={() => setEditing("new")}>
            <Plus aria-hidden /> New sale
          </Button>
        )}
      </header>
      {editing && (
        <PromotionForm
          key={editing === "new" ? "new" : editing.id}
          promo={editing === "new" ? null : editing}
          onDone={() => setEditing(null)}
        />
      )}
      {promos.isPending ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading promotions">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-24 rounded-card" />
          ))}
        </div>
      ) : promos.isError ? (
        <ErrorState message={toApiError(promos.error).message} onRetry={() => promos.refetch()} />
      ) : promos.data.length === 0 ? (
        !editing && (
          <EmptyState
            icon={Percent}
            title="No sales yet"
            description="Schedule a platform-wide sale, like an end-of-year sale, and boutiques can enter their pieces."
            action={
              <Button variant="primary" onClick={() => setEditing("new")}>
                New sale
              </Button>
            }
          />
        )
      ) : (
        <ul className="flex flex-col gap-3">
          {promos.data.map((p) => (
            <Row key={p.id} p={p} onEdit={() => setEditing(p)} />
          ))}
        </ul>
      )}
    </div>
  );
}

function Row({ p, onEdit }: { p: AdminPromotion; onEdit: () => void }) {
  const { cancel } = usePromotionActions();
  const s = STATE[p.state];
  const open = p.state === "upcoming" || p.state === "live";
  return (
    <li>
      <Card className="flex flex-wrap items-center gap-4 p-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-h3 text-ink">{p.title}</span>
            <Badge tone={s.tone} withIcon={false}>
              {s.label}
            </Badge>
            <span className="text-caption text-ink-muted">“{p.badge}”</span>
          </div>
          <span className="text-small text-ink-muted">
            {dateFmt.format(new Date(p.starts_at))} – {dateFmt.format(new Date(p.ends_at))} · {p.min_discount_percent}–
            {p.max_discount_percent}% · {p.product_count} pieces from {p.seller_count} boutiques
          </span>
        </div>
        {p.state === "live" && (
          <Button asChild variant="ghost" size="sm">
            <Link href={`/deals/${p.slug}`}>View</Link>
          </Button>
        )}
        {open && (
          <div className="flex">
            <Button size="icon" variant="ghost" aria-label={`Edit ${p.title}`} onClick={onEdit}>
              <Pencil aria-hidden />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              aria-label={`Cancel ${p.title}`}
              className="text-ink-muted hover:text-danger"
              loading={cancel.isPending && cancel.variables === p.id}
              onClick={() => {
                if (!window.confirm(`Cancel ${p.title}? Every sale price returns to normal now.`)) return;
                cancel.mutate(p.id, {
                  onSuccess: () => toast.success(`${p.title} cancelled; prices restored`),
                  onError: (e) => toast.error(toApiError(e).message),
                });
              }}
            >
              <Ban aria-hidden />
            </Button>
          </div>
        )}
      </Card>
    </li>
  );
}

function PromotionForm({ promo, onDone }: { promo: AdminPromotion | null; onDone: () => void }) {
  const { save } = usePromotionActions();
  const now = new Date();
  const week = new Date(now.getTime() + 7 * 864e5);
  const [title, setTitle] = useState(promo?.title ?? "");
  const [badge, setBadge] = useState(promo?.badge ?? "");
  const [description, setDescription] = useState(promo?.description ?? "");
  const [starts, setStarts] = useState(toLocalInput(promo?.starts_at ?? now.toISOString()));
  const [ends, setEnds] = useState(toLocalInput(promo?.ends_at ?? week.toISOString()));
  const [min, setMin] = useState(String(promo?.min_discount_percent ?? 10));
  const [max, setMax] = useState(String(promo?.max_discount_percent ?? 50));
  const [hero, setHero] = useState<GalleryItem | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErrors({});
    setError(null);
    try {
      const p = await save.mutateAsync({
        id: promo?.id,
        body: {
          title,
          badge,
          description: description || null,
          starts_at: new Date(starts).toISOString(),
          ends_at: new Date(ends).toISOString(),
          min_discount_percent: Number(min) || 1,
          max_discount_percent: Number(max) || 1,
          hero_asset_id: hero?.assetId ?? null,
        },
      });
      toast.success(promo ? `${p.title} updated` : `${p.title} scheduled`);
      onDone();
    } catch (err) {
      const api = toApiError(err);
      const f = fieldErrors(api);
      if (Object.keys(f).length) setErrors(f);
      else setError(api.message);
    }
  };

  return (
    <Card className="p-6">
      <form onSubmit={submit} noValidate className="flex flex-col gap-5">
        <h2 className="text-h3 text-ink">{promo ? `Edit ${promo.title}` : "New sale"}</h2>
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Title" error={errors.title}>
            <Input value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} placeholder="End of the Year Sale" />
          </Field>
          <Field label="Badge" error={errors.badge} hint="Short label on cards and banners.">
            <Input value={badge} maxLength={32} onChange={(e) => setBadge(e.target.value)} placeholder="Year-End Sale" />
          </Field>
          <Field label="Starts" error={errors.starts_at}>
            <Input type="datetime-local" value={starts} onChange={(e) => setStarts(e.target.value)} />
          </Field>
          <Field label="Ends" error={errors.ends_at}>
            <Input type="datetime-local" value={ends} onChange={(e) => setEnds(e.target.value)} />
          </Field>
          <Field label="Smallest discount (%)" error={errors.min_discount_percent}>
            <Input inputMode="numeric" value={min} onChange={(e) => setMin(e.target.value.replace(/\D/g, ""))} />
          </Field>
          <Field label="Largest discount (%)" error={errors.max_discount_percent} hint="Up to 90%.">
            <Input inputMode="numeric" value={max} onChange={(e) => setMax(e.target.value.replace(/\D/g, ""))} />
          </Field>
        </div>
        <Field label="Description" optional>
          <Textarea value={description} maxLength={1000} rows={3} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <SingleImageField
          label="Banner image"
          hint="Optional. Without one, the sale uses its pieces' photos."
          purpose="product"
          aspect="wide"
          url={hero?.url ?? promo?.hero_url ?? null}
          onUploaded={setHero}
        />
        <div className="flex gap-3">
          <Button type="submit" variant="primary" loading={save.isPending}>
            {promo ? "Save changes" : "Schedule sale"}
          </Button>
          <Button type="button" variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
