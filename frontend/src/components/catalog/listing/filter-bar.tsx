"use client";

import { ChevronDown, SlidersHorizontal, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Chip } from "@/components/ui/chip";
import { DialogTitle, Sheet, SheetContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select } from "@/components/ui/select";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/tabs";
import type { ApiSchemas } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";
import { activeFilterCount, SORTS, toggled, withValue } from "@/lib/listing-params";
import { cn } from "@/lib/utils";

type Facets = ApiSchemas["Facets"];
type FacetValue = ApiSchemas["FacetValue"];

const EXTRA_LABELS: Record<string, string> = {
  notes: "Notes", concentration: "Concentration", family: "Olfactory family", material: "Material",
  closure: "Closure", fit: "Fit", fabric: "Fabric", heel: "Heel height", upper: "Upper",
};
// The one category-specific facet promoted to the bar, per category.
const KEY_EXTRA: Record<string, string> = {
  perfumes: "family", bags: "material", clothing: "fabric", shoes: "heel", accessories: "material",
};

interface FilterBarProps {
  facets: Facets;
  total: number;
  category?: string;
  /** Hide dimensions that are fixed by the page (e.g. boutique pages). */
  hide?: ("boutique" | "subcategory")[];
  children: ReactNode;
}

/**
 * UX: Hick's Law — four key filters up front (Size, Color, Price and one
 * category-specific facet); everything else behind "More filters".
 * Filters live in the URL, so every result set is shareable (spec §9).
 */
export function FilterBar({ facets, total, category, hide = [], children }: FilterBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();
  const [sheet, setSheet] = useState(false);

  const go = (next: URLSearchParams) =>
    startTransition(() => router.push(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false }));
  const toggle = (key: string, value: string) => go(toggled(params, key, value));

  const keyExtra = category ? KEY_EXTRA[category] : undefined;
  const extraKeys = Object.keys(facets.extra).filter((k) => facets.extra[k]!.length > 1);
  const selected = (key: string) => params.getAll(key);
  const facetSelected = (k: string) => selected("facet").filter((f) => f.startsWith(`${k}:`)).map((f) => f.slice(k.length + 1));
  const count = activeFilterCount(params);

  const applied: { label: string; onRemove: () => void }[] = [
    ...selected("size").map((v) => ({ label: `Size ${v}`, onRemove: () => toggle("size", v) })),
    ...selected("color").map((v) => ({ label: v, onRemove: () => toggle("color", v) })),
    ...selected("brand").map((v) => ({ label: facets.brands.find((b) => b.value === v)?.label ?? v, onRemove: () => toggle("brand", v) })),
    ...selected("boutique").map((v) => ({ label: facets.boutiques.find((b) => b.value === v)?.label ?? v, onRemove: () => toggle("boutique", v) })),
    ...selected("condition").map((v) => ({ label: facets.conditions.find((c) => c.value === v)?.label ?? v, onRemove: () => toggle("condition", v) })),
    ...selected("facet").map((v) => ({ label: v.split(":")[1]!, onRemove: () => toggle("facet", v) })),
    ...(params.get("price_min") || params.get("price_max")
      ? [{
          label: `QC ${formatNumber(Number(params.get("price_min") ?? 0))}–${params.get("price_max") ? formatNumber(Number(params.get("price_max"))) : "∞"}`,
          onRemove: () => go(withValue(withValue(params, "price_min", null), "price_max", null)),
        }]
      : []),
    ...(params.get("in_stock") ? [{ label: "In stock", onRemove: () => go(withValue(params, "in_stock", null)) }] : []),
  ];

  const sizePanel = <ChipGroup values={facets.sizes} selected={selected("size")} onToggle={(v) => toggle("size", v)} />;
  const colorPanel = <ColorGroup values={facets.colors} selected={selected("color")} onToggle={(v) => toggle("color", v)} />;
  const pricePanel = (
    <PricePanel
      range={facets.price}
      min={params.get("price_min")}
      max={params.get("price_max")}
      onApply={(lo, hi) => go(withValue(withValue(params, "price_min", lo), "price_max", hi))}
    />
  );
  const extraPanel = (k: string) => (
    <CheckList values={facets.extra[k] ?? []} selected={facetSelected(k)} onToggle={(v) => toggle("facet", `${k}:${v}`)} />
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="sticky top-14 z-30 -mx-4 flex flex-col gap-3 border-b border-border bg-[var(--glass)] px-4 py-3 backdrop-blur-xl sm:-mx-6 sm:px-6 lg:-mx-10 lg:px-10">
        <div className="flex flex-wrap items-center gap-2">
          {/* Desktop: the four key filters */}
          <div className="hidden flex-wrap items-center gap-2 md:flex">
            {facets.sizes.length > 0 && <FilterPopover label="Size" active={selected("size").length}>{sizePanel}</FilterPopover>}
            {facets.colors.length > 0 && <FilterPopover label="Color" wide active={selected("color").length}>{colorPanel}</FilterPopover>}
            <FilterPopover label="Price" active={params.get("price_min") || params.get("price_max") ? 1 : 0}>{pricePanel}</FilterPopover>
            {keyExtra && facets.extra[keyExtra] && (
              <FilterPopover label={EXTRA_LABELS[keyExtra] ?? keyExtra} active={facetSelected(keyExtra).length}>
                {extraPanel(keyExtra)}
              </FilterPopover>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={() => setSheet(true)} className="gap-2">
            <SlidersHorizontal aria-hidden />
            <span className="md:hidden">Filters</span>
            <span className="hidden md:inline">More filters</span>
            {count > 0 && <span className="tabular rounded-pill bg-ink px-1.5 text-caption text-bg">{count}</span>}
          </Button>
          <div className="ml-auto flex items-center gap-3">
            <p className="tabular hidden text-small text-ink-muted sm:block" aria-live="polite">
              {pending ? "Updating…" : `${formatNumber(total)} ${total === 1 ? "piece" : "pieces"}`}
            </p>
            <label htmlFor="sort" className="sr-only">Sort by</label>
            <Select
              id="sort"
              value={params.get("sort") ?? "curated"}
              onChange={(e) => go(withValue(params, "sort", e.target.value === "curated" ? null : e.target.value))}
              className="h-11 w-52 rounded-pill text-small"
            >
              {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </Select>
          </div>
        </div>
        {applied.length > 0 && (
          <ul aria-label="Applied filters" className="flex flex-wrap items-center gap-2">
            {applied.map((a) => (
              <li key={a.label}>
                <button
                  type="button"
                  onClick={a.onRemove}
                  className="inline-flex h-9 items-center gap-1.5 rounded-pill bg-ink px-3 text-caption font-semibold text-bg"
                  aria-label={`Remove filter ${a.label}`}
                >
                  {a.label} <X aria-hidden className="size-3.5" />
                </button>
              </li>
            ))}
            <li>
              <Button variant="link" size="sm" onClick={() => go(new URLSearchParams(params.get("q") ? { q: params.get("q")! } : {}))}>
                Clear all
              </Button>
            </li>
          </ul>
        )}
      </div>

      <div className={cn("transition-opacity duration-[var(--dur-fast)]", pending && "pointer-events-none opacity-50")} aria-busy={pending}>
        {children}
      </div>

      {/* All filters — bottom sheet on mobile, side drawer on desktop. */}
      <Sheet open={sheet} onOpenChange={setSheet}>
        <SheetContent side="right" aria-describedby={undefined} className="gap-2">
          <DialogTitle>Filters</DialogTitle>
          <Accordion type="multiple" defaultValue={["size", "color", "price"]} className="flex-1">
            {!hide.includes("subcategory") && facets.subcategories.length > 1 && (
              <Group value="subcategory" title="Category">
                <CheckList values={facets.subcategories} selected={params.get("subcategory") ? [params.get("subcategory")!] : []} onToggle={(v) => go(withValue(params, "subcategory", params.get("subcategory") === v ? null : v))} />
              </Group>
            )}
            {facets.sizes.length > 0 && <Group value="size" title="Size">{sizePanel}</Group>}
            {facets.colors.length > 0 && <Group value="color" title="Color">{colorPanel}</Group>}
            <Group value="price" title="Price">{pricePanel}</Group>
            {extraKeys.map((k) => <Group key={k} value={k} title={EXTRA_LABELS[k] ?? k}>{extraPanel(k)}</Group>)}
            <Group value="brand" title="House">
              <CheckList values={facets.brands} selected={selected("brand")} onToggle={(v) => toggle("brand", v)} />
            </Group>
            {!hide.includes("boutique") && (
              <Group value="boutique" title="Boutique">
                <CheckList values={facets.boutiques} selected={selected("boutique")} onToggle={(v) => toggle("boutique", v)} />
              </Group>
            )}
            <Group value="condition" title="Condition">
              <CheckList values={facets.conditions} selected={selected("condition")} onToggle={(v) => toggle("condition", v)} />
            </Group>
            <Group value="stock" title="Availability">
              <label className="flex min-h-11 items-center gap-3 text-small">
                <Checkbox checked={!!params.get("in_stock")} onCheckedChange={(c) => go(withValue(params, "in_stock", c ? "true" : null))} />
                In stock only
              </label>
            </Group>
          </Accordion>
          <Button variant="secondary" size="lg" block onClick={() => setSheet(false)}>
            {pending ? "Updating…" : `Show ${formatNumber(total)} ${total === 1 ? "piece" : "pieces"}`}
          </Button>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function Group({ value, title, children }: { value: string; title: string; children: ReactNode }) {
  return (
    <AccordionItem value={value}>
      <AccordionTrigger>{title}</AccordionTrigger>
      <AccordionContent>{children}</AccordionContent>
    </AccordionItem>
  );
}

function FilterPopover({ label, active, wide, children }: { label: string; active: number; wide?: boolean; children: ReactNode }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex h-11 items-center gap-1.5 rounded-pill border px-4 text-small font-semibold transition-colors",
            active ? "border-ink bg-ink text-bg" : "border-border-strong bg-surface text-ink hover:border-ink",
          )}
        >
          {label}
          {active > 0 && <span className="tabular">· {active}</span>}
          <ChevronDown aria-hidden className="size-4" />
        </button>
      </PopoverTrigger>
      {/* Two columns of color names ("Heather grey", "Black wash") need more than w-72. */}
      <PopoverContent className={cn(wide && "w-96 max-w-[calc(100vw-2rem)]")}>{children}</PopoverContent>
    </Popover>
  );
}

function ChipGroup({ values, selected, onToggle }: { values: FacetValue[]; selected: string[]; onToggle: (v: string) => void }) {
  return (
    <div role="group" className="flex flex-wrap gap-2">
      {values.map((f) => (
        <Chip key={f.value} selected={selected.includes(f.value)} onClick={() => onToggle(f.value)} disabled={f.count === 0 && !selected.includes(f.value)} aria-label={`${f.label}, ${f.count} pieces`}>
          {f.label}
        </Chip>
      ))}
    </div>
  );
}

function ColorGroup({ values, selected, onToggle }: { values: FacetValue[]; selected: string[]; onToggle: (v: string) => void }) {
  return (
    <ul className="grid grid-cols-2 gap-1">
      {values.map((f) => {
        const on = selected.includes(f.value);
        return (
          <li key={f.value}>
            <button
              type="button"
              aria-pressed={on}
              onClick={() => onToggle(f.value)}
              className={cn("flex min-h-11 w-full items-center gap-2.5 rounded-input px-2 text-left text-small hover:bg-surface-muted", on && "bg-surface-muted font-semibold")}
            >
              <span className={cn("size-5 shrink-0 rounded-full border border-border-strong/50", on && "ring-2 ring-ink ring-offset-2 ring-offset-surface")} style={{ background: f.hex ?? undefined }} />
              <span className="flex-1 truncate">{f.label}</span>
              <span className="tabular text-caption text-ink-muted">{f.count}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function CheckList({ values, selected, onToggle }: { values: FacetValue[]; selected: string[]; onToggle: (v: string) => void }) {
  return (
    <ul className="flex max-h-72 flex-col overflow-y-auto">
      {values.map((f) => (
        <li key={f.value}>
          <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-input px-1 text-small hover:bg-surface-muted">
            <Checkbox checked={selected.includes(f.value)} onCheckedChange={() => onToggle(f.value)} />
            <span className="flex-1">{f.label}</span>
            <span className="tabular text-caption text-ink-muted">{f.count}</span>
          </label>
        </li>
      ))}
    </ul>
  );
}

function PricePanel({
  range,
  min,
  max,
  onApply,
}: {
  range: { min: number; max: number };
  min: string | null;
  max: string | null;
  onApply: (lo: string | null, hi: string | null) => void;
}) {
  const [lo, setLo] = useState(min ?? "");
  const [hi, setHi] = useState(max ?? "");
  // Postel's Law: "12,500", "12 500" and "12500" all mean 12500.
  const clean = (v: string) => v.replace(/[^\d]/g, "") || null;
  const presets: [string, number | null, number | null][] = [
    ["Under 5,000", null, 5000],
    ["5,000–15,000", 5000, 15000],
    ["15,000–40,000", 15000, 40000],
    ["40,000+", 40000, null],
  ];
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        onApply(clean(lo), clean(hi));
      }}
    >
      <p className="text-caption text-ink-muted">
        From QC {formatNumber(range.min)} to QC {formatNumber(range.max)}
      </p>
      <div className="flex flex-wrap gap-2">
        {presets.map(([label, a, b]) => (
          <Chip key={label} onClick={() => onApply(a?.toString() ?? null, b?.toString() ?? null)} className="h-9 px-3 text-caption">
            {label}
          </Chip>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Input aria-label="Minimum price in QC" inputMode="numeric" placeholder="Min" value={lo} onChange={(e) => setLo(e.target.value)} className="h-11" />
        <span aria-hidden>–</span>
        <Input aria-label="Maximum price in QC" inputMode="numeric" placeholder="Max" value={hi} onChange={(e) => setHi(e.target.value)} className="h-11" />
      </div>
      <Button type="submit" variant="secondary" size="sm">Apply</Button>
    </form>
  );
}
