"use client";

import { Minus, Plus } from "lucide-react";

import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

type Attrs = Record<string, unknown>;

type Spec =
  | { key: string; label: string; kind: "text"; hint?: string; optional?: boolean; placeholder?: string }
  | { key: string; label: string; kind: "number"; hint?: string; optional?: boolean; unit?: string; step?: number; min?: number; max?: number }
  | { key: string; label: string; kind: "select"; options: string[]; hint?: string }
  | { key: string; label: string; kind: "list"; hint?: string; optional?: boolean; placeholder?: string }
  | { key: string; label: string; kind: "chips"; options: string[]; hint?: string; optional?: boolean }
  | { key: string; label: string; kind: "scale"; hint?: string; low: string; high: string }
  | { key: string; label: string; kind: "composition"; hint?: string };

/**
 * Category-specific details (spec §9), mirroring the backend's Pydantic models.
 * UX: Tesler's Law — fixed choices are chips/selects, not free text, and the
 * composition editor adds up the percentages for the seller.
 */
export const ATTRIBUTE_SPECS: Record<string, Spec[]> = {
  clothing: [
    { key: "fit", label: "Fit", kind: "select", options: ["slim", "regular", "oversized"] },
    { key: "composition", label: "Fabric composition", kind: "composition", hint: "Must add up to 100%." },
    { key: "care", label: "Care", kind: "list", optional: true, placeholder: "Hand wash cold, Dry flat" },
    { key: "model_height_cm", label: "Model height", kind: "number", unit: "cm", optional: true, min: 140, max: 210 },
    { key: "model_size", label: "Model wears", kind: "text", optional: true, placeholder: "S" },
  ],
  shoes: [
    { key: "upper", label: "Upper", kind: "text", placeholder: "Calf leather" },
    { key: "lining", label: "Lining", kind: "text", placeholder: "Goatskin" },
    { key: "sole", label: "Sole", kind: "text", placeholder: "Leather with rubber insert" },
    { key: "heel_height_cm", label: "Heel height", kind: "number", unit: "cm", step: 0.5, min: 0, max: 15 },
    { key: "last", label: "Last / fit note", kind: "text", optional: true, placeholder: "Almond toe, narrow last" },
  ],
  bags: [
    { key: "width_cm", label: "Width", kind: "number", unit: "cm", step: 0.5, min: 0.5, max: 80 },
    { key: "height_cm", label: "Height", kind: "number", unit: "cm", step: 0.5, min: 0.5, max: 80 },
    { key: "depth_cm", label: "Depth", kind: "number", unit: "cm", step: 0.5, min: 0.5, max: 50 },
    { key: "material", label: "Material", kind: "text", placeholder: "Pebbled calf" },
    { key: "hardware_finish", label: "Hardware", kind: "text", placeholder: "Brushed gold" },
    { key: "closure", label: "Closure", kind: "text", placeholder: "Magnetic snap" },
    { key: "strap_drop_cm", label: "Strap drop", kind: "number", unit: "cm", optional: true, min: 0, max: 80 },
    { key: "interior", label: "Interior", kind: "text", placeholder: "Suede lining, one slip pocket" },
    { key: "fits", label: "What fits inside", kind: "chips", optional: true, options: ["phone", "wallet", "keys", "sunglasses", "tablet", "laptop", "water bottle"] },
  ],
  accessories: [
    { key: "material", label: "Material", kind: "text", placeholder: "18k gold vermeil" },
    { key: "stone", label: "Stone", kind: "text", optional: true, placeholder: "Freshwater pearl" },
    { key: "dimensions", label: "Dimensions", kind: "text", optional: true, placeholder: "2.5 cm drop" },
    { key: "water_resistance_m", label: "Water resistance", kind: "number", unit: "m", optional: true, min: 0, max: 500 },
    { key: "care", label: "Care", kind: "list", optional: true, placeholder: "Store dry, Polish gently" },
  ],
  perfumes: [
    { key: "concentration", label: "Concentration", kind: "select", options: ["Parfum", "EDP", "EDT", "EDC"] },
    { key: "family", label: "Olfactory family", kind: "select", options: ["Floral", "Woody", "Amber", "Fresh", "Citrus", "Gourmand", "Chypre", "Fougère", "Aromatic", "Leather"] },
    { key: "top_notes", label: "Top notes", kind: "list", placeholder: "Bergamot, Calamansi" },
    { key: "heart_notes", label: "Heart notes", kind: "list", placeholder: "Neroli, Sampaguita" },
    { key: "base_notes", label: "Base notes", kind: "list", placeholder: "Vetiver, Musk" },
    { key: "perfumer", label: "Perfumer", kind: "text", placeholder: "Ines Cruz" },
    { key: "longevity", label: "Longevity", kind: "scale", low: "Fleeting", high: "All day" },
    { key: "sillage", label: "Sillage", kind: "scale", low: "Intimate", high: "Fills the room" },
    { key: "seasons", label: "Seasons", kind: "chips", optional: true, options: ["spring", "summer", "autumn", "winter"] },
    { key: "occasions", label: "Occasions", kind: "list", optional: true, placeholder: "Office, Evening" },
  ],
};

const listToText = (v: unknown) => (Array.isArray(v) ? v.join(", ") : "");
const textToList = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export function AttributeFields({ category, value, onChange }: { category: string; value: Attrs; onChange: (v: Attrs) => void }) {
  const specs = ATTRIBUTE_SPECS[category] ?? [];
  const set = (key: string, v: unknown) => {
    const next = { ...value };
    if (v === "" || v === null || v === undefined || (Array.isArray(v) && v.length === 0)) delete next[key];
    else next[key] = v;
    onChange(next);
  };

  return (
    <div className="grid gap-5 sm:grid-cols-2">
      {specs.map((s) => {
        const optional = "optional" in s && s.optional;
        const wide = s.kind === "composition" || s.kind === "chips" || s.kind === "list";
        const cls = wide ? "sm:col-span-2" : "";
        switch (s.kind) {
          case "text":
            return (
              <Field key={s.key} label={s.label} optional={optional} hint={s.hint} className={cls}>
                <Input value={String(value[s.key] ?? "")} placeholder={s.placeholder} onChange={(e) => set(s.key, e.target.value)} />
              </Field>
            );
          case "number":
            return (
              <Field key={s.key} label={`${s.label}${s.unit ? ` (${s.unit})` : ""}`} optional={optional} hint={s.hint} className={cls}>
                <Input type="number" inputMode="decimal" step={s.step ?? 1} min={s.min} max={s.max} value={value[s.key] === undefined ? "" : String(value[s.key])}
                  onChange={(e) => set(s.key, e.target.value === "" ? null : Number(e.target.value))} />
              </Field>
            );
          case "select":
            return (
              <Field key={s.key} label={s.label} hint={s.hint} className={cls}>
                <Select value={String(value[s.key] ?? "")} onChange={(e) => set(s.key, e.target.value)}>
                  <option value="" disabled>Choose…</option>
                  {s.options.map((o) => <option key={o} value={o}>{o[0]!.toUpperCase() + o.slice(1)}</option>)}
                </Select>
              </Field>
            );
          case "list":
            return (
              <Field key={s.key} label={s.label} optional={optional} hint={s.hint ?? "Separate with commas."} className={cls}>
                <ListInput value={value[s.key]} placeholder={s.placeholder} onCommit={(list) => set(s.key, list)} />
              </Field>
            );
          case "chips": {
            const on = (Array.isArray(value[s.key]) ? value[s.key] : []) as string[];
            return (
              <fieldset key={s.key} className={cn("flex flex-col gap-2", cls)}>
                <legend className="mb-1 text-small font-semibold text-ink">{s.label}{optional && <span className="font-normal text-ink-muted"> (optional)</span>}</legend>
                <div className="flex flex-wrap gap-2">
                  {s.options.map((o) => (
                    <button key={o} type="button" aria-pressed={on.includes(o)} onClick={() => set(s.key, on.includes(o) ? on.filter((x) => x !== o) : [...on, o])}
                      className="h-11 rounded-pill border border-border-strong px-4 text-small font-semibold capitalize aria-pressed:border-ink aria-pressed:bg-ink aria-pressed:text-bg">
                      {o}
                    </button>
                  ))}
                </div>
              </fieldset>
            );
          }
          case "scale": {
            const n = Number(value[s.key] ?? 0);
            return (
              <fieldset key={s.key} className={cn("flex flex-col gap-2", cls)}>
                <legend className="mb-1 text-small font-semibold text-ink">{s.label}</legend>
                <div className="flex items-center gap-1" role="radiogroup" aria-label={s.label}>
                  {[1, 2, 3, 4, 5].map((i) => (
                    <button key={i} type="button" role="radio" aria-checked={n === i} aria-label={`${i} of 5`} onClick={() => set(s.key, i)}
                      className={cn("h-11 flex-1 rounded-input border text-small font-semibold", i <= n ? "border-accent-2 bg-accent-2 text-on-accent-2" : "border-border-strong text-ink-muted")}>
                      {i}
                    </button>
                  ))}
                </div>
                <div className="flex justify-between text-caption text-ink-muted"><span>{s.low}</span><span>{s.high}</span></div>
              </fieldset>
            );
          }
          case "composition":
            return <Composition key={s.key} value={value[s.key]} onChange={(v) => set(s.key, v)} className={cls} />;
        }
      })}
    </div>
  );
}

/** Text that becomes a list on blur, so typing "Bergamot, " isn't interrupted. */
function ListInput({ value, placeholder, onCommit, ...rest }: { value: unknown; placeholder?: string; onCommit: (l: string[]) => void; id?: string }) {
  return (
    <Input
      {...rest}
      key={listToText(value)}
      defaultValue={listToText(value)}
      placeholder={placeholder}
      onBlur={(e) => onCommit(textToList(e.target.value))}
    />
  );
}

type Share = { fiber: string; pct: number };

function Composition({ value, onChange, className }: { value: unknown; onChange: (v: Share[]) => void; className?: string }) {
  const rows: Share[] = Array.isArray(value) && value.length ? (value as Share[]) : [{ fiber: "", pct: 100 }];
  const total = rows.reduce((a, r) => a + (Number(r.pct) || 0), 0);
  const update = (i: number, patch: Partial<Share>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <fieldset className={cn("flex flex-col gap-2", className)}>
      <legend className="mb-1 text-small font-semibold text-ink">Fabric composition</legend>
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input aria-label={`Fiber ${i + 1}`} placeholder="Silk" value={r.fiber} onChange={(e) => update(i, { fiber: e.target.value })} />
          <Input aria-label={`Percent of fiber ${i + 1}`} type="number" min={1} max={100} value={r.pct} onChange={(e) => update(i, { pct: Number(e.target.value) })} className="w-24" />
          <span className="text-small text-ink-muted">%</span>
          <button type="button" aria-label={`Remove fiber ${i + 1}`} disabled={rows.length === 1} onClick={() => onChange(rows.filter((_, j) => j !== i))} className="grid size-11 shrink-0 place-items-center rounded-full disabled:opacity-30 hover:bg-surface-muted">
            <Minus aria-hidden className="size-4" />
          </button>
        </div>
      ))}
      <div className="flex items-center justify-between">
        <button type="button" onClick={() => onChange([...rows, { fiber: "", pct: Math.max(1, 100 - total) }])} className="inline-flex min-h-11 items-center gap-1 text-small font-semibold text-accent-2 hover:underline">
          <Plus aria-hidden className="size-4" /> Add fiber
        </button>
        <span className={cn("tabular text-small font-semibold", total === 100 ? "text-success" : "text-warning")} aria-live="polite">
          Total {total}%{total !== 100 && " — must be 100%"}
        </span>
      </div>
    </fieldset>
  );
}
