/**
 * Listing filter state lives in the URL (spec §9: shareable results). URL
 * param names match the API's query params one to one.
 */
export type SearchParams = Record<string, string | string[] | undefined>;

export const MULTI_KEYS = ["brand", "boutique", "size", "color", "condition", "facet"] as const;
export const SINGLE_KEYS = ["q", "sort", "price_min", "price_max", "in_stock", "subcategory"] as const;
export type MultiKey = (typeof MULTI_KEYS)[number];

/** UX: Choice Overload — six sort options, curated by default. */
export const SORTS = [
  { value: "curated", label: "Curated for you" },
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "most_wished", label: "Most wished" },
  { value: "top_rated", label: "Top rated" },
] as const;

export function asArray(v: string | string[] | undefined): string[] {
  if (v === undefined) return [];
  return Array.isArray(v) ? v : [v];
}

/** Only the params the listing understands, in API shape. */
export function toApiQuery(sp: SearchParams, fixed: Record<string, string> = {}) {
  const out: Record<string, string | string[]> = { ...fixed };
  for (const k of MULTI_KEYS) {
    const vals = asArray(sp[k]).filter(Boolean);
    if (vals.length) out[k] = vals;
  }
  for (const k of SINGLE_KEYS) {
    const v = asArray(sp[k])[0];
    if (v) out[k] = v;
  }
  return out;
}

export function toggled(params: URLSearchParams, key: string, value: string): URLSearchParams {
  const next = new URLSearchParams(params);
  const all = next.getAll(key);
  next.delete(key);
  const has = all.includes(value);
  for (const v of all) if (v !== value) next.append(key, v);
  if (!has) next.append(key, value);
  next.delete("cursor");
  return next;
}

export function withValue(params: URLSearchParams, key: string, value: string | null): URLSearchParams {
  const next = new URLSearchParams(params);
  if (value === null || value === "") next.delete(key);
  else next.set(key, value);
  next.delete("cursor");
  return next;
}

export function activeFilterCount(params: URLSearchParams): number {
  let n = 0;
  for (const k of MULTI_KEYS) n += params.getAll(k).length;
  if (params.get("price_min") || params.get("price_max")) n += 1;
  if (params.get("in_stock")) n += 1;
  return n;
}
