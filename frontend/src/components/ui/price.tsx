import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

/** The small wallet glyph that marks every Que Credits amount. */
export function QcGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden
      className={cn("inline-block size-[0.9em] shrink-0", className)}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
    >
      <rect x="1.5" y="3.5" width="13" height="10" rx="2.5" />
      <path d="M1.5 6.5h9a2 2 0 0 1 2 2v0a2 2 0 0 1-2 2h-1" />
      <circle cx="10.5" cy="8.5" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

interface PriceProps {
  amount: number;
  /** Shown struck-through only for real markdowns (no fake reference prices). */
  compareAt?: number | null;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeClass = { sm: "text-small", md: "text-body", lg: "text-h3" } as const;

/**
 * The one price style everywhere (Gestalt: Similarity): "QC 12,500" with the
 * wallet glyph and tabular numerals so columns of prices align.
 */
export function Price({ amount, compareAt, size = "md", className }: PriceProps) {
  const onSale = compareAt != null && compareAt > amount;
  return (
    <span className={cn("inline-flex flex-wrap items-baseline gap-x-2", className)}>
      <span
        className={cn("tabular inline-flex items-center gap-1 font-bold text-ink", sizeClass[size])}
      >
        <QcGlyph className="self-center text-accent-2" />
        <span>
          <span className="sr-only">Price: </span>QC {formatNumber(amount)}
        </span>
      </span>
      {onSale && (
        <s className="tabular text-small text-ink-muted">
          <span className="sr-only">Was </span>QC {formatNumber(compareAt)}
        </s>
      )}
    </span>
  );
}
