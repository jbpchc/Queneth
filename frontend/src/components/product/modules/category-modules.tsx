import { CupSoda, Glasses, KeyRound, Laptop, Smartphone, Tablet, Wallet, type LucideIcon } from "lucide-react";
import Image from "next/image";

import type { ApiSchemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

import { FragrancePyramid } from "./fragrance-pyramid";
import { SHOE_SIZES } from "./size-guide";

type Detail = ApiSchemas["ProductDetail"];
type Attrs = Record<string, unknown>;

/** One tailored module per category (spec §9). */
export function CategoryModule({ product }: { product: Detail }) {
  const a = product.attributes as Attrs;
  switch (product.category.slug) {
    case "perfumes":
      return <FragrancePyramid attrs={a} />;
    case "shoes":
      return <ShoeFit attrs={a} sizes={product.sizes} verdict={product.review_summary.fit_verdict} fit={product.review_summary.fit} />;
    case "bags":
      return <BagDimensions attrs={a} />;
    case "accessories":
      return <AccessoryCare attrs={a} images={product.images.filter((_, i) => i === 1 || i >= 3).slice(0, 3)} />;
    case "clothing":
      return <ClothingFit attrs={a} fit={product.review_summary.fit} verdict={product.review_summary.fit_verdict} />;
    default:
      return null;
  }
}

function ModuleShell({ kicker, title, children, className }: { kicker: string; title: string; children: React.ReactNode; className?: string }) {
  return (
    <section aria-labelledby="module-title" className={cn("rounded-card border border-border bg-surface p-6 shadow-1 md:p-10", className)}>
      <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">{kicker}</p>
      <h2 id="module-title" className="mb-8 mt-1 text-h2 text-ink">{title}</h2>
      {children}
    </section>
  );
}

const VERDICT = {
  runs_small: { label: "Runs small", hint: "Most buyers went half a size up." },
  true_to_size: { label: "True to size", hint: "Most buyers took their usual size." },
  runs_large: { label: "Runs large", hint: "Most buyers went half a size down." },
} as const;

/** Small / True / Large meter built from review fit votes. */
function FitMeter({ fit, verdict }: { fit: Record<string, number> | null; verdict: keyof typeof VERDICT | null }) {
  if (!fit || !verdict) {
    return <p className="text-small text-ink-muted">No fit feedback yet. Reviews from verified buyers will build this meter.</p>;
  }
  const position = { runs_small: 12, true_to_size: 50, runs_large: 88 }[verdict];
  return (
    <div className="flex flex-col gap-3">
      <p className="text-h3 font-display text-ink">{VERDICT[verdict].label}</p>
      <p className="text-small text-ink-muted">{VERDICT[verdict].hint}</p>
      <div className="relative mt-2 h-2 rounded-pill bg-surface-muted" role="img" aria-label={`Fit: ${VERDICT[verdict].label}`}>
        <span className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-ink shadow-1" style={{ left: `${position}%` }} />
      </div>
      <div className="flex justify-between text-caption text-ink-muted">
        <span>Small · {fit.small}%</span><span>True · {fit.true}%</span><span>Large · {fit.large}%</span>
      </div>
    </div>
  );
}

function ClothingFit({ attrs, fit, verdict }: { attrs: Attrs; fit: Record<string, number> | null; verdict: Detail["review_summary"]["fit_verdict"] }) {
  const comp = (attrs.composition as { fiber: string; pct: number }[]) ?? [];
  return (
    <ModuleShell kicker="Size & fit" title="How it wears">
      <div className="grid gap-10 md:grid-cols-3">
        <div>
          <h3 className="mb-2 font-sans text-small font-bold uppercase tracking-[0.1em] text-ink-muted">Cut</h3>
          <p className="text-h3 font-display capitalize text-ink">{String(attrs.fit)} fit</p>
          {Boolean(attrs.model_height_cm) && (
            <p className="mt-2 text-small text-ink-muted">Model is {String(attrs.model_height_cm)} cm and wears size {String(attrs.model_size)}.</p>
          )}
        </div>
        <div>
          <h3 className="mb-2 font-sans text-small font-bold uppercase tracking-[0.1em] text-ink-muted">Cloth</h3>
          <ul className="flex flex-col gap-2">
            {comp.map((f) => (
              <li key={f.fiber} className="flex flex-col gap-1">
                <span className="flex justify-between text-small"><span className="capitalize">{f.fiber}</span><span className="tabular">{f.pct}%</span></span>
                <span className="h-1.5 rounded-pill bg-surface-muted"><span className="block h-full rounded-pill bg-ink" style={{ width: `${f.pct}%` }} /></span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 font-sans text-small font-bold uppercase tracking-[0.1em] text-ink-muted">Buyers say</h3>
          <FitMeter fit={fit} verdict={verdict} />
        </div>
      </div>
    </ModuleShell>
  );
}

function ShoeFit({ attrs, sizes, verdict, fit }: { attrs: Attrs; sizes: string[]; verdict: Detail["review_summary"]["fit_verdict"]; fit: Record<string, number> | null }) {
  const offered = new Set(sizes.map(Number));
  return (
    <ModuleShell kicker="Size & fit" title="Size conversion">
      <div className="grid gap-10 md:grid-cols-[1.4fr_1fr]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] text-small">
            <caption className="sr-only">Shoe size conversion</caption>
            <thead className="text-left text-caption uppercase tracking-[0.08em] text-ink-muted">
              <tr><th scope="col" className="py-2">EU</th><th scope="col">UK</th><th scope="col">US (W)</th><th scope="col">US (M)</th><th scope="col">Foot (cm)</th></tr>
            </thead>
            <tbody className="tabular divide-y divide-border">
              {SHOE_SIZES.map(([eu, uk, usw, usm, cm]) => (
                <tr key={eu} className={cn(!offered.has(eu) && "text-ink-muted/60")}>
                  <th scope="row" className="py-2 text-left font-semibold">{eu}</th><td>{uk}</td><td>{usw}</td><td>{usm}</td><td>{cm}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-col gap-6">
          <div>
            <h3 className="mb-2 font-sans text-small font-bold uppercase tracking-[0.1em] text-ink-muted">The last</h3>
            <p className="text-ink">{String(attrs.last ?? "Standard last")}</p>
            <p className="mt-1 text-small text-ink-muted">Heel {String(attrs.heel_height_cm)} cm · {String(attrs.sole)}</p>
          </div>
          <div>
            <h3 className="mb-2 font-sans text-small font-bold uppercase tracking-[0.1em] text-ink-muted">Buyers say</h3>
            <FitMeter fit={fit} verdict={verdict} />
          </div>
        </div>
      </div>
    </ModuleShell>
  );
}

const FITS: Record<string, { icon: LucideIcon; label: string }> = {
  phone: { icon: Smartphone, label: "Phone" }, wallet: { icon: Wallet, label: "Wallet" },
  keys: { icon: KeyRound, label: "Keys" }, sunglasses: { icon: Glasses, label: "Sunglasses" },
  tablet: { icon: Tablet, label: "Tablet" }, laptop: { icon: Laptop, label: "13\" laptop" },
  "water bottle": { icon: CupSoda, label: "Water bottle" },
};

/** Bags: proportional dimension diagram + "What fits" row (spec §9). */
function BagDimensions({ attrs }: { attrs: Attrs }) {
  const w = Number(attrs.width_cm), h = Number(attrs.height_cm), d = Number(attrs.depth_cm);
  const scale = 200 / Math.max(w, h);
  const W = w * scale, H = h * scale, D = Math.min(d * scale * 0.5, 60);
  const fits = (attrs.fits as string[]) ?? [];
  return (
    <ModuleShell kicker="Dimensions" title="What fits inside">
      <div className="grid items-center gap-10 md:grid-cols-2">
        <svg viewBox={`0 0 ${W + D + 90} ${H + D + 70}`} className="mx-auto w-full max-w-md text-ink" role="img" aria-label={`${w} by ${h} by ${d} centimetres`}>
          <g transform={`translate(40 ${D + 10})`} fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d={`M0 0 H${W} V${H} H0 Z`} className="fill-[var(--surface-muted)]" />
            <path d={`M0 0 L${D} ${-D} H${W + D} V${H - D} L${W} ${H} M${W} 0 L${W + D} ${-D}`} strokeOpacity="0.55" />
            <g className="fill-current" stroke="none" fontSize="13" fontFamily="var(--font-manrope)">
              <text x={W / 2} y={H + 30} textAnchor="middle">{w} cm</text>
              <text x={-12} y={H / 2} textAnchor="end" dominantBaseline="middle">{h} cm</text>
              <text x={W + D / 2 + 8} y={-D / 2 - 6}>{d} cm</text>
            </g>
            <path d={`M0 ${H + 14} H${W} M0 ${H + 9} V${H + 19} M${W} ${H + 9} V${H + 19}`} strokeWidth="1" />
          </g>
        </svg>
        <div className="flex flex-col gap-6">
          <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4">
            {Object.entries(FITS).map(([key, { icon: Icon, label }]) => {
              const ok = fits.includes(key);
              return (
                <li key={key} className={cn("flex flex-col items-center gap-1.5 rounded-input p-3 text-center text-caption", ok ? "bg-success-soft text-ink" : "text-ink-muted/50")}>
                  <Icon aria-hidden className="size-6" />
                  <span>{label}</span>
                  <span className="sr-only">{ok ? "fits" : "doesn't fit"}</span>
                </li>
              );
            })}
          </ul>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-small">
            <dt className="text-ink-muted">Material</dt><dd>{String(attrs.material)}</dd>
            <dt className="text-ink-muted">Hardware</dt><dd>{String(attrs.hardware_finish)}</dd>
            <dt className="text-ink-muted">Closure</dt><dd>{String(attrs.closure)}</dd>
            {attrs.strap_drop_cm != null && (<><dt className="text-ink-muted">Strap drop</dt><dd>{String(attrs.strap_drop_cm)} cm</dd></>)}
          </dl>
        </div>
      </div>
    </ModuleShell>
  );
}

/** Accessories: material close-ups + care card (spec §9). */
function AccessoryCare({ attrs, images }: { attrs: Attrs; images: ApiSchemas["ImageOut"][] }) {
  const care = (attrs.care as string[]) ?? [];
  return (
    <ModuleShell kicker="Materials" title="Up close">
      <div className="grid gap-8 md:grid-cols-[1.5fr_1fr]">
        <ul className="grid grid-cols-3 gap-3">
          {images.map((img) => (
            <li key={img.url} className="relative aspect-square overflow-hidden rounded-input bg-surface-muted">
              <Image src={img.url} alt={img.alt} fill sizes="(min-width: 768px) 18vw, 30vw" className="object-cover" />
            </li>
          ))}
        </ul>
        <div className="rounded-card bg-surface-muted p-6">
          <h3 className="mb-4 font-display text-h3 text-ink">Care card</h3>
          <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2 text-small">
            <dt className="text-ink-muted">Material</dt><dd>{String(attrs.material)}</dd>
            {Boolean(attrs.stone) && attrs.stone !== "None" && (<><dt className="text-ink-muted">Stone</dt><dd>{String(attrs.stone)}</dd></>)}
            {Boolean(attrs.dimensions) && (<><dt className="text-ink-muted">Size</dt><dd>{String(attrs.dimensions)}</dd></>)}
            {attrs.water_resistance_m != null && (<><dt className="text-ink-muted">Water resistance</dt><dd>{String(attrs.water_resistance_m)} m</dd></>)}
          </dl>
          <ul className="flex flex-col gap-2 text-small">
            {care.map((c) => <li key={c} className="flex gap-2"><span aria-hidden>·</span>{c}</li>)}
          </ul>
        </div>
      </div>
    </ModuleShell>
  );
}
