"use client";

import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  selected?: boolean;
}

/**
 * The one chip style (Gestalt: Similarity) used for filters, sizes and sort.
 * Selected chips invert to ink and give a small spring "pop" on press.
 */
export const Chip = forwardRef<HTMLButtonElement, ChipProps>(
  ({ className, selected = false, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      aria-pressed={selected}
      className={cn(
        // UX: Fitts's Law — 44px minimum hit area.
        "inline-flex h-11 min-w-11 items-center justify-center gap-1.5 rounded-pill border px-4 text-small font-semibold",
        "transition-[background-color,color,border-color,transform] duration-[var(--dur-fast)] ease-brand",
        "motion-safe:active:scale-95",
        selected
          ? "border-ink bg-ink text-bg"
          : "border-border-strong bg-surface text-ink hover:border-ink",
        "disabled:cursor-not-allowed disabled:border-dashed disabled:text-ink-muted disabled:line-through",
        className,
      )}
      {...props}
    />
  ),
);
Chip.displayName = "Chip";
