"use client";

import { SearchX } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { ProductGrid } from "@/components/catalog/product-card";
import { Button } from "@/components/ui/button";
import { ProductCardSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { api, toApiError, type ApiSchemas } from "@/lib/api/client";

type Listing = ApiSchemas["ProductListing"];

/**
 * First page is server-rendered; "Load more" fetches the next batch of 24
 * (UX: Miller's Law) with the same filters and appends it.
 */
export function ListingResults({
  initial,
  query,
  emptyTitle = "Nothing matches — yet",
  emptyHint = "Try removing a filter or two. New pieces arrive every week.",
}: {
  initial: Listing;
  query: Record<string, string | string[]>;
  emptyTitle?: string;
  emptyHint?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [items, setItems] = useState(initial.items);
  const [cursor, setCursor] = useState(initial.next_cursor);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadMore() {
    if (!cursor) return;
    setLoading(true);
    setError(null);
    const { data, error: err } = await api.GET("/api/v1/catalog/products", {
      params: { query: { ...query, cursor } as never },
    });
    setLoading(false);
    if (err || !data) {
      setError(toApiError(err).message);
      return;
    }
    setItems((prev) => [...prev, ...data.items]);
    setCursor(data.next_cursor);
  }

  if (items.length === 0) {
    return (
      // UX: Paradox of the Active User — an empty result always offers a next step.
      <EmptyState
        icon={SearchX}
        title={emptyTitle}
        description={emptyHint}
        action={
          <Button variant="secondary" onClick={() => router.push(pathname)}>
            Clear filters
          </Button>
        }
      />
    );
  }

  return (
    <div className="flex flex-col gap-12">
      <ProductGrid cards={items} pickId={initial.connoisseur_pick_id} />
      {loading && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-10 sm:grid-cols-3 lg:grid-cols-4" aria-busy="true" aria-label="Loading more pieces">
          {Array.from({ length: 4 }, (_, i) => <ProductCardSkeleton key={i} />)}
        </div>
      )}
      {error && <ErrorState message={error} onRetry={loadMore} />}
      <div className="flex flex-col items-center gap-3">
        <p className="tabular text-small text-ink-muted">
          Showing {items.length} of {initial.total}
        </p>
        {cursor && !loading && (
          <Button variant="outline" size="lg" onClick={loadMore}>
            Load more
          </Button>
        )}
      </div>
    </div>
  );
}
