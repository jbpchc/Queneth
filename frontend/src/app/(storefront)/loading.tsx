import { ProductCardSkeleton, Skeleton } from "@/components/ui/skeleton";

/** Route-level skeleton matching the listing grid (UX: Doherty Threshold). */
export default function Loading() {
  return (
    <div
      className="mx-auto max-w-[1536px] px-4 py-10 sm:px-6 lg:px-10"
      aria-busy="true"
      aria-label="Loading"
    >
      <Skeleton className="mb-8 h-12 w-2/3 max-w-xl" />
      <div className="grid grid-cols-2 gap-x-4 gap-y-10 md:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <ProductCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}
