import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * UX: Doherty Threshold — skeletons match the final layout so the page feels
 * instant and nothing shifts when data lands (CLS < 0.1).
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden
      className={cn(
        "rounded-input bg-surface-muted motion-safe:animate-[skeleton-pulse_1.6s_ease-in-out_infinite]",
        className,
      )}
      {...props}
    />
  );
}

/** Skeleton shaped exactly like a product card: 4:5 image, brand, name, price. */
export function ProductCardSkeleton() {
  return (
    <div className="flex flex-col gap-3" role="presentation">
      <Skeleton className="aspect-[4/5] w-full rounded-card" />
      <Skeleton className="h-3 w-1/3" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/4" />
    </div>
  );
}
