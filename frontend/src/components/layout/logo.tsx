import Link from "next/link";

import { cn } from "@/lib/utils";

/** UX: Jakob's Law — logo top-left, always links home. */
export function Logo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <Link
      href="/"
      aria-label="Queneth home"
      className={cn(
        "inline-flex items-baseline font-display font-semibold tracking-[-0.03em] text-ink transition-[font-size] duration-[var(--dur-base)] ease-brand",
        compact ? "text-[1.5rem]" : "text-[1.75rem]",
        className,
      )}
      style={{ fontVariationSettings: '"opsz" 144' }}
    >
      Queneth
      <span aria-hidden className="ml-0.5 text-accent">
        .
      </span>
    </Link>
  );
}
