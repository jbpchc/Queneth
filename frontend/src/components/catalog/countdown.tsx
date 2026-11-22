"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

function parts(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return { d: Math.floor(s / 86400), h: Math.floor((s % 86400) / 3600), m: Math.floor((s % 3600) / 60), s: s % 60 };
}

/**
 * Elegant countdown to a *real* scheduled time (never a fake timer, spec §6).
 * Announces politely at most once a minute, not every second.
 */
export function Countdown({ to, className, onDone }: { to: string; className?: string; onDone?: () => void }) {
  const target = new Date(to).getTime();
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    setNow(Date.now());
    const t = setInterval(() => {
      const n = Date.now();
      setNow(n);
      if (n >= target) {
        clearInterval(t);
        onDone?.();
      }
    }, 1000);
    return () => clearInterval(t);
  }, [target, onDone]);

  const p = parts(now === null ? target - Date.parse(to) + 1 : target - now);
  const units: [number, string][] = [
    [p.d, "days"],
    [p.h, "hrs"],
    [p.m, "min"],
    [p.s, "sec"],
  ];
  return (
    <div className={cn("flex items-stretch gap-2", className)}>
      <span className="sr-only" aria-live="polite">
        {now !== null && `Goes live in ${p.d} days, ${p.h} hours and ${p.m} minutes`}
      </span>
      {units.map(([v, label]) => (
        <div
          key={label}
          aria-hidden
          className="flex min-w-14 flex-col items-center rounded-input border border-current/15 bg-current/[0.04] px-2 py-1.5"
        >
          <span className="tabular font-display text-h3 leading-none">{now === null ? "––" : String(v).padStart(2, "0")}</span>
          <span className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] opacity-70">{label}</span>
        </div>
      ))}
    </div>
  );
}
