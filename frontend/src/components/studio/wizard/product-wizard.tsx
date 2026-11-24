"use client";

import { Check, CircleAlert, ExternalLink, Loader2, Minus, Plus, Rocket } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { SortableImages, type GalleryItem } from "@/components/studio/uploads";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, ErrorState } from "@/components/ui/states";
import { toApiError, type ApiSchemas } from "@/lib/api/client";
import { formatQc, optionLabel } from "@/lib/format";
import { useProductActions, useStudioMeta, useStudioProduct, type StudioMeta, type StudioProduct } from "@/lib/studio";
import { cn } from "@/lib/utils";

import { AttributeFields } from "./attribute-fields";
import { saveLabel, useAutosave } from "./use-autosave";

const STEPS = [
  { id: "basics", label: "Basics" },
  { id: "media", label: "Media" },
  { id: "variants", label: "Variants & stock" },
  { id: "details", label: "Category details" },
  { id: "pricing", label: "Pricing" },
  { id: "review", label: "Preview & publish" },
] as const;
type StepId = (typeof STEPS)[number]["id"];

interface Row {
  key: string;
  id?: string;
  options: Record<string, string>;
  price: string;
  compare: string;
  stock: string;
  threshold: string;
}

interface Draft {
  title: string;
  brand: string;
  category: string;
  subcategory: string;
  condition: "new" | "pre-loved" | "vintage";
  description: string;
  authenticity: string;
  tags: string;
  attributes: Record<string, unknown>;
  images: GalleryItem[];
  rows: Row[];
}

const num = (s: string) => Number(String(s).replace(/[^\d]/g, "")) || 0;
let seq = 0;
const key = () => `row-${++seq}`;

function fromProduct(p: StudioProduct): Draft {
  return {
    title: p.title,
    brand: p.brand,
    category: p.category,
    subcategory: p.subcategory,
    condition: (p.condition as Draft["condition"]) ?? "new",
    description: p.description,
    authenticity: p.authenticity_note ?? "",
    tags: p.tags.join(", "),
    attributes: p.attributes,
    images: p.images.map((i, n) => ({ key: `img-${n}-${i.url}`, url: i.url, text: i.alt, color: i.color ?? null })),
    rows: p.variants.map((v) => ({
      key: v.id,
      id: v.id,
      options: v.options,
      price: String(v.price_qc),
      compare: v.compare_at_qc ? String(v.compare_at_qc) : "",
      stock: String(v.stock),
      threshold: String(v.low_stock_threshold),
    })),
  };
}

function rowComplete(r: Row, axes: string[]): boolean {
  return Object.keys(r.options).length > 0 && Object.keys(r.options).every((k) => axes.includes(k)) && num(r.price) > 0;
}

function toPatch(d: Draft, axes: string[]): ApiSchemas["ProductPatch"] {
  const patch: ApiSchemas["ProductPatch"] = {
    title: d.title.trim() || undefined,
    brand: d.brand.trim() || undefined,
    category: d.category,
    subcategory: d.subcategory,
    condition: d.condition,
    description: d.description,
    authenticity_note: d.authenticity.trim() || null,
    tags: d.tags.split(",").map((t) => t.trim()).filter(Boolean),
    attributes: d.attributes,
    images: d.images.map((i, n) => ({
      ...(i.assetId ? { asset_id: i.assetId } : { url: i.url }),
      alt: i.text.trim().length >= 3 ? i.text.trim() : `${d.title || "Product"}, photo ${n + 1}`,
      // Keep the color tag: the shop shows this photo when that swatch is picked.
      color: i.color || null,
    })),
  };
  // Half-typed variant rows are held back so they never fail a save.
  if (d.rows.every((r) => rowComplete(r, axes))) {
    patch.variants = d.rows.map((r) => ({
      ...(r.id ? { id: r.id } : {}),
      options: r.options,
      price_qc: num(r.price),
      compare_at_qc: r.compare ? num(r.compare) : null,
      stock: num(r.stock),
      low_stock_threshold: r.threshold === "" ? 3 : num(r.threshold),
    }));
  }
  return patch;
}

/**
 * Six-step product wizard (spec §10). Step 1 creates the draft; every later
 * change autosaves. Publishing is the last step and lists what's missing.
 * UX: Goal-Gradient (progress bar), Zeigarnik (what's left), Chunking (steps),
 * Miller's Law (≤ 6 steps).
 */
export function ProductWizard({ productId }: { productId: string | null }) {
  const meta = useStudioMeta();
  const product = useStudioProduct(productId);

  if (meta.isPending || (productId && product.isPending)) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading the wizard">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-2 w-full rounded-pill" />
        <Skeleton className="h-96 rounded-card" />
      </div>
    );
  }
  if (meta.isError) return <ErrorState message={toApiError(meta.error).message} onRetry={() => meta.refetch()} />;
  if (productId && product.isError) return <ErrorState message={toApiError(product.error).message} onRetry={() => product.refetch()} />;
  if (!productId) return <NewProduct meta={meta.data} />;
  return <Editor key={product.data!.id} meta={meta.data} initial={product.data!} />;
}

// ─── Step 1 for a brand-new piece ──────────────────────────────────────────

function NewProduct({ meta }: { meta: StudioMeta }) {
  const router = useRouter();
  const { create } = useProductActions();
  const [title, setTitle] = useState("");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [sub, setSub] = useState("");
  const [condition, setCondition] = useState<Draft["condition"]>("new");
  const [error, setError] = useState<string | null>(null);
  const subs = meta.categories.find((c) => c.slug === category)?.subcategories ?? [];
  // Brand is optional: left empty, the piece is listed under the boutique name.
  const ready = title.trim().length >= 3 && brand.trim().length !== 1 && category && sub;

  return (
    <div className="flex flex-col gap-6">
      <WizardHeader title="Add a product" step={0} done={[]} onStep={() => {}} newPiece saveText="Drafts save automatically after this step" />
      <Card className="flex flex-col gap-5 p-6">
        <BasicsFields
          meta={meta}
          v={{ title, brand, category, subcategory: sub, condition }}
          set={(p) => {
            if (p.title !== undefined) setTitle(p.title);
            if (p.brand !== undefined) setBrand(p.brand);
            if (p.category !== undefined) { setCategory(p.category); setSub(""); }
            if (p.subcategory !== undefined) setSub(p.subcategory);
            if (p.condition !== undefined) setCondition(p.condition);
          }}
          subs={subs}
        />
        {error && <Alert tone="danger">{error}</Alert>}
        <Button
          variant="primary"
          size="lg"
          className="self-start"
          disabled={!ready}
          loading={create.isPending}
          onClick={async () => {
            setError(null);
            try {
              const p = await create.mutateAsync({ title, brand: brand.trim() || null, category, subcategory: sub, condition });
              router.replace(`/seller/products/${p.id}?step=media`);
            } catch (err) {
              setError(toApiError(err).message);
            }
          }}
        >
          Create draft &amp; continue
        </Button>
      </Card>
    </div>
  );
}

// ─── Editor for an existing draft or live piece ────────────────────────────

function Editor({ meta, initial }: { meta: StudioMeta; initial: StudioProduct }) {
  const router = useRouter();
  const search = useSearchParams();
  const { patch, publish } = useProductActions();
  const [server, setServer] = useState(initial);
  const [d, setD] = useState<Draft>(() => fromProduct(initial));
  const step = (STEPS.find((s) => s.id === search.get("step"))?.id ?? "basics") as StepId;
  const stepIndex = STEPS.findIndex((s) => s.id === step);
  const cat = meta.categories.find((c) => c.slug === d.category);
  const axes = cat?.variant_axes ?? [];

  const { state, flush } = useAutosave(d, async (value) => {
    const saved = await patch.mutateAsync({ id: server.id, body: toPatch(value, axes) });
    setServer(saved);
    // Adopt ids/urls the server assigned to new rows and uploads (same order).
    setD((cur) => ({
      ...cur,
      rows: cur.rows.map((r, i) => (!r.id && saved.variants[i] && cur.rows.length === saved.variants.length ? { ...r, id: saved.variants[i]!.id } : r)),
      images: cur.images.map((img, i) => (img.assetId && saved.images[i] && cur.images.length === saved.images.length ? { ...img, assetId: undefined, url: saved.images[i]!.url } : img)),
    }));
  });

  const go = (id: StepId) => {
    void flush();
    router.replace(`/seller/products/${server.id}?step=${id}`, { scroll: false });
    window.scrollTo({ top: 0 });
  };

  const done = useMemo(() => {
    const m = server.missing;
    const out: StepId[] = ["basics"];
    if (server.images.length) out.push("media");
    if (server.variants.length) out.push("variants", "pricing");
    if (!m.some((x) => x.startsWith("Category details"))) out.push("details");
    if (server.status === "active") out.push("review");
    return out;
  }, [server]);

  const set = (p: Partial<Draft>) => setD((cur) => ({ ...cur, ...p }));
  const next = STEPS[stepIndex + 1];

  return (
    <div className="flex flex-col gap-6">
      <WizardHeader
        title={d.title || "Untitled piece"}
        status={server.status}
        step={stepIndex}
        done={done}
        onStep={(i) => go(STEPS[i]!.id)}
        saveText={
          state.kind !== "error" && state.kind !== "saving" && d.rows.some((r) => !rowComplete(r, axes))
            ? "Saved, except variants still missing an option or price"
            : saveLabel(state)
        }
        saveError={state.kind === "error"}
        saving={state.kind === "saving"}
      />

      <Card className="flex flex-col gap-6 p-6">
        <h2 className="text-h3 text-ink">{STEPS[stepIndex]!.label}</h2>

        {step === "basics" && (
          <>
            <BasicsFields
              meta={meta}
              v={d}
              subs={cat?.subcategories ?? []}
              locked={server.status !== "draft"}
              set={(p) => set({ ...p, ...(p.category && p.category !== d.category ? { attributes: {}, subcategory: "", rows: [] } : {}) })}
            />
            <Field label="Description" hint={`What it is, how it's made, how it wears. ${d.description.trim().length}/40 minimum.`}>
              <Textarea rows={6} value={d.description} maxLength={5000} onChange={(e) => set({ description: e.target.value })} />
            </Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Authenticity note" optional hint="Provenance, certificates, condition notes.">
                <Textarea rows={3} value={d.authenticity} maxLength={1000} onChange={(e) => set({ authenticity: e.target.value })} />
              </Field>
              <Field label="Tags" optional hint="Comma-separated, e.g. quiet-luxury, evening.">
                <Input value={d.tags} onChange={(e) => set({ tags: e.target.value })} />
              </Field>
            </div>
          </>
        )}

        {step === "media" && (
          <div className="flex flex-col gap-3">
            <SortableImages
              label="Photos"
              purpose="product"
              items={d.images}
              onChange={(images) => set({ images })}
              max={10}
              textLabel="Alt text"
              textPlaceholder="Describe the photo"
              colors={[...new Set(d.rows.map((r) => r.options.color).filter((c): c is string => !!c))]}
            />
            {axes.includes("color") && (
              <p className="text-caption text-ink-muted">
                {d.rows.some((r) => r.options.color)
                  ? "Tag each photo with the color it shows, so shoppers see the right photo when they pick a swatch."
                  : "Add colors in Variants & stock, then come back to tag each photo with its color."}
              </p>
            )}
          </div>
        )}

        {step === "variants" && <VariantsStep axes={axes} rows={d.rows} onChange={(rows) => set({ rows })} />}

        {step === "details" && (
          <>
            <p className="text-small text-ink-muted">These power filters and the {cat?.name.toLowerCase()} module on the product page.</p>
            <AttributeFields category={d.category} value={d.attributes} onChange={(attributes) => set({ attributes })} />
          </>
        )}

        {step === "pricing" && <PricingStep rows={d.rows} onChange={(rows) => set({ rows })} />}

        {step === "review" && (
          <ReviewStep
            p={server}
            pending={state.kind === "pending" || state.kind === "saving"}
            publishing={publish.isPending}
            onFix={(m) => go(m.startsWith("Category") ? "details" : m.includes("photo") ? "media" : m.includes("variant") ? "variants" : "basics")}
            onPublish={async () => {
              await flush();
              try {
                const p = await publish.mutateAsync(server.id);
                setServer(p);
                toast.success("It's live", { description: `${p.title} is now in the catalog.` });
              } catch (err) {
                toast.error(toApiError(err).message);
              }
            }}
          />
        )}
      </Card>

      <div className="flex justify-between gap-3">
        <Button variant="ghost" disabled={stepIndex === 0} onClick={() => go(STEPS[stepIndex - 1]!.id)}>Back</Button>
        {next && <Button variant="secondary" onClick={() => go(next.id)}>Continue to {next.label.toLowerCase()}</Button>}
      </div>
    </div>
  );
}

function WizardHeader({
  title,
  status,
  step,
  done,
  onStep,
  saveText,
  saveError,
  saving,
  newPiece,
}: {
  newPiece?: boolean;
  title: string;
  status?: string;
  step: number;
  done: StepId[];
  onStep: (i: number) => void;
  saveText: string;
  saveError?: boolean;
  saving?: boolean;
}) {
  return (
    <header className="flex flex-col gap-4">
      <nav aria-label="Breadcrumb" className="text-small text-ink-muted">
        <Link href="/seller/products" className="hover:underline">Products</Link> / {title}
      </nav>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-h2 text-ink">{title}</h1>
        {status && (
          <Badge tone={status === "active" ? "success" : status === "removed" ? "danger" : "neutral"} withIcon={false}>
            {status === "active" ? "Live" : status === "archived" ? "Archived" : status === "removed" ? "Taken down" : "Draft"}
          </Badge>
        )}
        <span className={cn("ml-auto inline-flex items-center gap-1.5 text-small", saveError ? "text-danger" : "text-ink-muted")} role="status" aria-live="polite">
          {saving ? <Loader2 aria-hidden className="size-4 animate-spin" /> : saveError ? <CircleAlert aria-hidden className="size-4" /> : <Check aria-hidden className="size-4" />}
          {saveText}
        </span>
      </div>
      <Progress value={step + 1} max={STEPS.length} label={`Step ${step + 1} of ${STEPS.length}`} showValue={false} />
      <ol className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
        {STEPS.map((s, i) => (
          <li key={s.id} className="shrink-0">
            <button type="button" onClick={() => onStep(i)} aria-current={i === step ? "step" : undefined} disabled={newPiece && i > 0}
              title={newPiece && i > 0 ? "Create the draft first" : undefined}
              className={cn("inline-flex h-11 items-center gap-2 rounded-pill border px-4 text-small font-semibold disabled:opacity-40", i === step ? "border-ink bg-ink text-bg" : "border-border-strong text-ink hover:bg-surface-muted")}>
              {done.includes(s.id) && i !== step ? <Check aria-hidden className="size-4 text-success" /> : <span className="tabular">{i + 1}</span>}
              {s.label}
            </button>
          </li>
        ))}
      </ol>
    </header>
  );
}

function BasicsFields({
  meta,
  v,
  set,
  subs,
  locked,
}: {
  meta: StudioMeta;
  v: Pick<Draft, "title" | "brand" | "category" | "subcategory" | "condition">;
  set: (p: Partial<Draft>) => void;
  subs: Record<string, string>[];
  locked?: boolean;
}) {
  return (
    <>
      <Field label="Title" hint="Name the piece, not the brand: “Bias-cut silk slip”.">
        <Input value={v.title} maxLength={120} onChange={(e) => set({ title: e.target.value })} />
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Brand" optional hint="Leave empty to list it under your boutique name.">
          <Input list="studio-brands" value={v.brand} maxLength={60} onChange={(e) => set({ brand: e.target.value })} />
        </Field>
        <datalist id="studio-brands">{meta.brands.map((b) => <option key={b} value={b} />)}</datalist>
        <Field label="Condition">
          <Select value={v.condition} onChange={(e) => set({ condition: e.target.value as Draft["condition"] })}>
            <option value="new">New</option>
            <option value="pre-loved">Pre-loved</option>
            <option value="vintage">Vintage</option>
          </Select>
        </Field>
        <Field label="Category" hint={locked ? "Published pieces keep their category. Duplicate to change it." : undefined}>
          <Select value={v.category} disabled={locked} onChange={(e) => set({ category: e.target.value })}>
            <option value="" disabled>Choose…</option>
            {meta.categories.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
          </Select>
        </Field>
        <Field label="Type">
          <Select value={v.subcategory} disabled={!v.category} onChange={(e) => set({ subcategory: e.target.value })}>
            <option value="" disabled>{v.category ? "Choose…" : "Choose a category first"}</option>
            {subs.map((s) => <option key={s.slug} value={s.slug}>{s.name}</option>)}
          </Select>
        </Field>
      </div>
    </>
  );
}

const AXIS_HINT: Record<string, string> = { size: "S, M, 38, Mini…", color: "Ivory, Noir…", width: "Regular, Wide", volume: "50 ml" };

function VariantsStep({ axes, rows, onChange }: { axes: string[]; rows: Row[]; onChange: (r: Row[]) => void }) {
  const update = (i: number, p: Partial<Row>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  const add = () => {
    const last = rows[rows.length - 1];
    onChange([...rows, { key: key(), options: last ? { ...last.options } : {}, price: last?.price ?? "", compare: "", stock: "0", threshold: "3" }]);
  };
  const incomplete = rows.some((r) => !rowComplete(r, axes));
  return (
    <div className="flex flex-col gap-4">
      <p className="text-small text-ink-muted">One row per option combination. Leave an axis blank if it doesn&apos;t apply. Markdowns are set in the Pricing step.</p>
      {rows.length === 0 && <p className="text-small font-semibold text-ink">No variants yet.</p>}
      <div className="flex flex-col gap-3">
        {rows.map((r, i) => (
          <div key={r.key} className={cn("grid items-end gap-3 rounded-input border p-3", rowComplete(r, axes) ? "border-border" : "border-warning")} style={{ gridTemplateColumns: `repeat(${axes.length}, minmax(0,1fr)) 120px 88px 88px 44px` }}>
            {axes.map((a) => (
              <label key={a} className="flex min-w-0 flex-col gap-1 text-caption font-semibold capitalize text-ink">
                {a}
                <Input value={r.options[a] ?? ""} placeholder={AXIS_HINT[a]} onChange={(e) => {
                  const options = { ...r.options };
                  if (e.target.value.trim()) options[a] = e.target.value;
                  else delete options[a];
                  update(i, { options });
                }} />
              </label>
            ))}
            <label className="flex flex-col gap-1 text-caption font-semibold text-ink">Price (QC)<Input inputMode="numeric" value={r.price} onChange={(e) => update(i, { price: e.target.value.replace(/[^\d]/g, "") })} /></label>
            <label className="flex flex-col gap-1 text-caption font-semibold text-ink">Stock<Input inputMode="numeric" value={r.stock} onChange={(e) => update(i, { stock: e.target.value.replace(/\D/g, "") })} /></label>
            <label className="flex flex-col gap-1 text-caption font-semibold text-ink">Alert at<Input inputMode="numeric" value={r.threshold} onChange={(e) => update(i, { threshold: e.target.value.replace(/\D/g, "") })} /></label>
            <button type="button" aria-label={`Remove variant ${i + 1}`} onClick={() => onChange(rows.filter((_, j) => j !== i))} className="grid size-11 place-items-center rounded-full text-ink-muted hover:bg-surface-muted hover:text-danger">
              <Minus aria-hidden className="size-4" />
            </button>
          </div>
        ))}
      </div>
      <Button variant="outline" className="self-start" onClick={add}><Plus aria-hidden /> Add variant</Button>
      {incomplete && rows.length > 0 && (
        <p className="text-small text-warning">Highlighted rows need at least one option and a price before they save.</p>
      )}
    </div>
  );
}

function PricingStep({ rows, onChange }: { rows: Row[]; onChange: (r: Row[]) => void }) {
  const update = (i: number, p: Partial<Row>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  if (!rows.length) return <p className="text-small text-ink-muted">Add variants first, then price them here.</p>;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-small text-ink-muted">Prices in whole QC. Only add an original price for a genuine markdown; it must be higher than the selling price.</p>
      {rows.map((r, i) => {
        const bad = r.compare !== "" && num(r.compare) <= num(r.price);
        return (
          <div key={r.key} className="grid items-end gap-3 rounded-input border border-border p-3 sm:grid-cols-[1fr_160px_160px]">
            <span className="text-small font-semibold text-ink">{optionLabel(r.options) || `Variant ${i + 1}`}</span>
            <label className="flex flex-col gap-1 text-caption font-semibold text-ink">Price (QC)<Input inputMode="numeric" value={r.price} onChange={(e) => update(i, { price: e.target.value.replace(/[^\d]/g, "") })} /></label>
            <label className="flex flex-col gap-1 text-caption font-semibold text-ink">
              Original price <span className="font-normal text-ink-muted">(optional)</span>
              <Input inputMode="numeric" aria-invalid={bad || undefined} value={r.compare} onChange={(e) => update(i, { compare: e.target.value.replace(/[^\d]/g, "") })} />
            </label>
            {bad && <p className="text-small text-danger sm:col-span-3">The original price must be higher than {formatQc(num(r.price))}.</p>}
          </div>
        );
      })}
    </div>
  );
}

function ReviewStep({ p, pending, publishing, onFix, onPublish }: { p: StudioProduct; pending: boolean; publishing: boolean; onFix: (m: string) => void; onPublish: () => void }) {
  const prices = p.variants.map((v) => v.price_qc);
  const min = prices.length ? Math.min(...prices) : 0;
  const max = prices.length ? Math.max(...prices) : 0;
  const stock = p.variants.reduce((a, v) => a + v.stock, 0);
  const complete = p.missing.length === 0;
  return (
    <div className="grid gap-6 md:grid-cols-[240px_1fr]">
      {/* Preview as shoppers will see the card. */}
      <div className="flex flex-col gap-2">
        <div className="relative aspect-[4/5] overflow-clip rounded-card bg-surface-muted">
          {p.images[0] && <Image src={p.images[0].url} alt={p.images[0].alt} fill sizes="240px" className="object-cover" />}
        </div>
        <p className="text-caption font-bold uppercase tracking-[0.1em] text-ink-muted">{p.brand}</p>
        <p className="font-semibold text-ink">{p.title}</p>
        <p className="tabular text-small text-ink">{prices.length ? (min === max ? formatQc(min) : `${formatQc(min)} – ${formatQc(max)}`) : "No price yet"}</p>
      </div>
      <div className="flex flex-col gap-4">
        {complete ? (
          <Alert tone="success" title={p.status === "active" ? "Live in the catalog" : "Ready to publish"}>
            {p.variants.length} {p.variants.length === 1 ? "variant" : "variants"} · {stock} in stock · {p.images.length} {p.images.length === 1 ? "photo" : "photos"}
            {p.scheduled_drop && <> · goes live with the drop “{p.scheduled_drop}”</>}
          </Alert>
        ) : (
          <div className="flex flex-col gap-2" role="status">
            <p className="font-semibold text-ink">Almost there. Still needed:</p>
            <ul className="flex flex-col gap-1.5">
              {p.missing.map((m) => (
                <li key={m}>
                  <button type="button" onClick={() => onFix(m)} className="inline-flex min-h-11 items-center gap-2 text-left text-small text-warning hover:underline">
                    <CircleAlert aria-hidden className="size-4 shrink-0" /> {m}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {p.status === "active" ? (
          <div className="flex flex-wrap gap-3">
            <Button asChild variant="outline"><Link href={`/p/${p.slug}`} target="_blank">View product page <ExternalLink aria-hidden /></Link></Button>
            <Button asChild variant="ghost"><Link href="/seller/drops">Add to a drop</Link></Button>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" size="lg" disabled={!complete || pending} loading={publishing} onClick={onPublish}>
              <Rocket aria-hidden /> Publish now
            </Button>
            <Button asChild variant="ghost"><Link href="/seller/drops">Or schedule it in a drop</Link></Button>
          </div>
        )}
      </div>
    </div>
  );
}
