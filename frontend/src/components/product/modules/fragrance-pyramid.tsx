"use client";

import { motion, useReducedMotion } from "motion/react";

import { cn } from "@/lib/utils";

const TIERS = [
  { key: "top_notes", label: "Top", hint: "The first 15 minutes" },
  { key: "heart_notes", label: "Heart", hint: "The next few hours" },
  { key: "base_notes", label: "Base", hint: "What lingers" },
] as const;

/**
 * Perfumes: animated fragrance pyramid + longevity and sillage meters
 * (spec §9). Tiers rise in sequence when scrolled into view; with reduced
 * motion they simply fade in.
 */
export function FragrancePyramid({ attrs }: { attrs: Record<string, unknown> }) {
  const reduce = useReducedMotion();
  const notes = (k: string) => (attrs[k] as string[]) ?? [];
  return (
    <section aria-labelledby="pyramid-title" className="grain overflow-hidden rounded-card bg-ink p-6 text-bg md:p-10">
      <div className="relative z-[2] grid gap-10 md:grid-cols-[1.3fr_1fr]">
        <div>
          <p className="text-caption font-bold uppercase tracking-[0.14em] opacity-70">
            {String(attrs.concentration)} · {String(attrs.family)}
          </p>
          <h2 id="pyramid-title" className="mb-8 mt-1 text-h2">The fragrance pyramid</h2>
          <ol className="flex flex-col items-center gap-3">
            {TIERS.map((tier, i) => (
              <motion.li
                key={tier.key}
                initial={reduce ? { opacity: 0 } : { opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.4 }}
                transition={{ delay: (2 - i) * 0.18, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                // Wider tiers toward the base: the pyramid shape.
                className={cn(
                  "flex w-full flex-col items-center gap-2 rounded-card border border-current/15 bg-current/[0.04] px-4 py-4 text-center",
                  i === 0 && "max-w-[62%]",
                  i === 1 && "max-w-[81%]",
                )}
              >
                <span className="text-caption font-bold uppercase tracking-[0.14em] opacity-70">
                  {tier.label} <span className="font-normal normal-case tracking-normal">· {tier.hint}</span>
                </span>
                <span className="flex flex-wrap justify-center gap-1.5">
                  {notes(tier.key).map((n) => (
                    <span key={n} className="rounded-pill bg-bg/10 px-3 py-1 text-small capitalize">{n}</span>
                  ))}
                </span>
              </motion.li>
            ))}
          </ol>
        </div>
        <div className="flex flex-col justify-center gap-8">
          <Meter label="Longevity" value={Number(attrs.longevity)} low="Fleeting" high="All day and beyond" />
          <Meter label="Sillage" value={Number(attrs.sillage)} low="Skin scent" high="Fills the room" />
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-small">
            <dt className="opacity-70">Perfumer</dt><dd>{String(attrs.perfumer)}</dd>
            <dt className="opacity-70">Seasons</dt><dd className="capitalize">{((attrs.seasons as string[]) ?? []).join(", ") || "All year"}</dd>
            <dt className="opacity-70">Wear it for</dt><dd className="capitalize">{((attrs.occasions as string[]) ?? []).join(", ")}</dd>
          </dl>
        </div>
      </div>
    </section>
  );
}

function Meter({ label, value, low, high }: { label: string; value: number; low: string; high: string }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <span className="font-semibold">{label}</span>
        <span className="tabular text-small opacity-70">{value} / 5</span>
      </div>
      <div role="meter" aria-label={label} aria-valuemin={1} aria-valuemax={5} aria-valuenow={value} className="grid grid-cols-5 gap-1.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <span key={n} className={cn("h-2 rounded-pill", n <= value ? "bg-lilac" : "bg-bg/15")} />
        ))}
      </div>
      <div className="flex justify-between text-caption opacity-60">
        <span>{low}</span>
        <span>{high}</span>
      </div>
    </div>
  );
}
