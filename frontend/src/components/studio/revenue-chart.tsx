"use client";

import { useState } from "react";

import { formatQc } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Point {
  day: string;
  revenue_qc: number;
  orders: number;
}

const dayFmt = new Intl.DateTimeFormat("en-PH", { month: "short", day: "numeric" });
const parse = (d: string) => new Date(`${d}T00:00:00+08:00`);

/** "Nice" axis maximum: 1, 2 or 5 × a power of ten above the data. */
function niceMax(v: number): number {
  if (v <= 0) return 1000;
  const p = 10 ** Math.floor(Math.log10(v));
  return ([1, 2, 5, 10].find((m) => m * p >= v) ?? 10) * p;
}

/**
 * 30-day revenue, one bar per Manila day. Single series → one hue (the
 * accent-2 token, validated ≥3:1 on both surfaces), no legend; the title names it.
 * Hover/focus a day for its exact value; "Show as table" gives the same data in text.
 */
export function RevenueChart({ series, title = "Revenue, last 30 days" }: { series: Point[]; title?: string }) {
  const [active, setActive] = useState<number | null>(null);
  const [table, setTable] = useState(false);
  const max = niceMax(Math.max(...series.map((p) => p.revenue_qc)));
  const W = 600;
  const H = 180;
  const slot = W / series.length;
  const bar = Math.max(2, slot - 2); // 2px surface gap between bars
  const ticks = [0, max / 2, max];
  const a = active !== null ? series[active] : null;

  return (
    <figure className="flex flex-col gap-3">
      <figcaption className="flex items-baseline justify-between gap-4">
        <span className="text-small font-semibold text-ink">{title}</span>
        <button type="button" onClick={() => setTable((t) => !t)} className="min-h-11 text-small font-semibold text-accent-2 hover:underline">
          {table ? "Show as chart" : "Show as table"}
        </button>
      </figcaption>

      {table ? (
        <div className="max-h-72 overflow-y-auto rounded-input border border-border">
          <table className="w-full text-small">
            <thead className="sticky top-0 bg-surface text-left text-ink-muted">
              <tr><th className="px-3 py-2 font-semibold">Day</th><th className="px-3 py-2 text-right font-semibold">Orders</th><th className="px-3 py-2 text-right font-semibold">Revenue</th></tr>
            </thead>
            <tbody>
              {[...series].reverse().map((p) => (
                <tr key={p.day} className="border-t border-border">
                  <td className="px-3 py-1.5">{dayFmt.format(parse(p.day))}</td>
                  <td className="tabular px-3 py-1.5 text-right">{p.orders}</td>
                  <td className="tabular px-3 py-1.5 text-right">{formatQc(p.revenue_qc)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative">
          {/* Tooltip: text tokens only; the bar itself carries the color. */}
          <div className={cn("pointer-events-none absolute -top-1 right-0 rounded-input border border-border bg-surface px-3 py-1.5 text-small shadow-2 transition-opacity", a ? "opacity-100" : "opacity-0")} aria-live="polite">
            {a && (
              <>
                <span className="text-ink-muted">{dayFmt.format(parse(a.day))} · </span>
                <span className="tabular font-semibold text-ink">{formatQc(a.revenue_qc)}</span>
                <span className="text-ink-muted"> · {a.orders} {a.orders === 1 ? "order" : "orders"}</span>
              </>
            )}
          </div>
          <svg viewBox={`0 0 ${W + 56} ${H + 28}`} className="w-full" role="img" aria-label={`${title}: daily values, peaking at ${formatQc(Math.max(...series.map((p) => p.revenue_qc)))}`} onMouseLeave={() => setActive(null)}>
            {ticks.map((t) => {
              const y = H - (t / max) * H + 8;
              return (
                <g key={t}>
                  <line x1={0} x2={W} y1={y} y2={y} stroke="var(--border)" strokeWidth={1} />
                  <text x={W + 6} y={y + 4} className="fill-[var(--ink-muted)] text-[11px] tabular">{t >= 1000 ? `${Math.round(t / 1000)}k` : t}</text>
                </g>
              );
            })}
            {series.map((p, i) => {
              const h = (p.revenue_qc / max) * H;
              const x = i * slot + 1;
              const y = H - h + 8;
              const r = Math.min(4, bar / 2, h);
              return (
                <g key={p.day}>
                  {/* Hit target taller and wider than the mark. */}
                  <rect
                    x={i * slot}
                    y={0}
                    width={slot}
                    height={H + 8}
                    fill="transparent"
                    tabIndex={0}
                    aria-label={`${dayFmt.format(parse(p.day))}: ${formatQc(p.revenue_qc)}, ${p.orders} orders`}
                    onMouseEnter={() => setActive(i)}
                    onFocus={() => setActive(i)}
                    onBlur={() => setActive(null)}
                    className="outline-none focus-visible:fill-[var(--surface-muted)]"
                  />
                  {h > 0 && (
                    // 4px rounded data-end, square at the baseline.
                    <path
                      d={`M${x},${H + 8} V${y + r} Q${x},${y} ${x + r},${y} H${x + bar - r} Q${x + bar},${y} ${x + bar},${y + r} V${H + 8} Z`}
                      fill="var(--accent-2)"
                      opacity={active === null || active === i ? 1 : 0.45}
                      pointerEvents="none"
                    />
                  )}
                </g>
              );
            })}
            <line x1={0} x2={W} y1={H + 8} y2={H + 8} stroke="var(--border-strong)" strokeWidth={1} />
            {[0, 14, 29].map((i) => series[i] && (
              <text key={i} x={i * slot + slot / 2} y={H + 24} textAnchor={i === 0 ? "start" : i === 29 ? "end" : "middle"} className="fill-[var(--ink-muted)] text-[11px]">
                {dayFmt.format(parse(series[i]!.day))}
              </text>
            ))}
          </svg>
        </div>
      )}
    </figure>
  );
}
