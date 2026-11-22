import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface ProgressProps {
  value: number;
  max?: number;
  label: string;
  showValue?: boolean;
  tone?: "ink" | "accent" | "wallet" | "lilac";
  className?: string;
}

const toneClass = {
  ink: "bg-ink",
  accent: "bg-accent",
  wallet: "bg-accent-2",
  lilac: "bg-lilac",
} as const;

/**
 * UX: Goal-Gradient effect — visible progress toward a goal (checkout steps,
 * profile completion, tier progress, seller onboarding) speeds people up.
 */
export function Progress({
  value,
  max = 100,
  label,
  showValue = true,
  tone = "ink",
  className,
}: ProgressProps) {
  const pct = Math.max(0, Math.min(100, Math.round((value / max) * 100)));
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-baseline justify-between gap-4 text-small">
        <span className="font-semibold text-ink">{label}</span>
        {showValue && <span className="tabular text-ink-muted">{pct}%</span>}
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-2 w-full overflow-hidden rounded-pill bg-surface-muted"
      >
        <div
          className={cn(
            "h-full rounded-pill transition-[width] duration-[var(--dur-base)] ease-brand",
            toneClass[tone],
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

interface ProgressRingProps {
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  label: string;
  children?: ReactNode;
  className?: string;
}

/** Circular progress for the Connoisseur tier card. */
export function ProgressRing({
  value,
  max = 100,
  size = 112,
  stroke = 8,
  label,
  children,
  className,
}: ProgressRingProps) {
  const pct = Math.max(0, Math.min(1, value / max));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct * 100)}
      className={cn("relative inline-grid place-items-center", className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={stroke}
          className="stroke-surface-muted"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          className="stroke-lilac transition-[stroke-dashoffset] duration-[var(--dur-celebrate)] ease-brand"
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}
