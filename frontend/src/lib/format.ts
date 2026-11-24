const qcFormatter = new Intl.NumberFormat("en-PH", { maximumFractionDigits: 0 });

/** "QC 12,500". Amounts are integers end to end; never floats. */
export function formatQc(amount: number): string {
  return `QC ${qcFormatter.format(Math.trunc(amount))}`;
}

/** Plain thousands formatting without the currency prefix. */
export function formatNumber(value: number): string {
  return qcFormatter.format(value);
}

/**
 * UX: Miller's Law — show long identifiers in readable chunks.
 * "QN20264821O7" → "QN-2026-4821-07"; already-chunked values pass through.
 */
export function chunkReference(ref: string, sizes: number[] = [2, 4, 4, 2]): string {
  const raw = ref.replace(/[\s-]/g, "").toUpperCase();
  const parts: string[] = [];
  let i = 0;
  for (const size of sizes) {
    if (i >= raw.length) break;
    parts.push(raw.slice(i, i + size));
    i += size;
  }
  if (i < raw.length) parts.push(raw.slice(i));
  return parts.join("-");
}

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function formatRelative(date: Date | string, now: Date = new Date()): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const seconds = Math.round((d.getTime() - now.getTime()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["week", 604_800],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

const OPTION_ORDER = ["color", "metal", "size", "volume", "width"];

/**
 * A variant's options in one fixed order: "Purple · M". Stored key order
 * varies (Postgres JSONB puts shorter keys first, "size" before "color").
 */
export function optionLabel(options: Record<string, string>, sep = " · "): string {
  const rank = (k: string) => (OPTION_ORDER.includes(k) ? OPTION_ORDER.indexOf(k) : OPTION_ORDER.length);
  return Object.keys(options)
    .sort((a, b) => rank(a) - rank(b))
    .map((k) => options[k])
    .join(sep);
}
