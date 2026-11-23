"use client";

import { ExternalLink, Plus } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useBoutiqueSettings } from "@/lib/studio";

/**
 * Top of the Seller Studio sidebar: which store you're managing, a link to see
 * it as buyers do, and the most common task one click away.
 * UX: Fitts's Law — "Add a product" is a large, always-visible target.
 */
export function StoreCard() {
  const store = useBoutiqueSettings();
  return (
    <div className="flex flex-col gap-3 rounded-card border border-border bg-bg p-3">
      {store.isPending ? (
        <Skeleton className="h-10 rounded-input" />
      ) : store.data ? (
        <div className="flex items-center gap-3">
          <span className="relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-full bg-surface-muted text-small font-bold text-ink">
            {store.data.logo_url ? (
              <Image src={store.data.logo_url} alt="" fill sizes="40px" className="object-cover" />
            ) : (
              store.data.boutique_name.slice(0, 1)
            )}
          </span>
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-small font-semibold text-ink">{store.data.boutique_name}</span>
            <Link
              href={`/b/${store.data.slug}`}
              className="inline-flex items-center gap-1 text-caption font-medium text-accent-2 hover:underline"
            >
              View your store <ExternalLink aria-hidden className="size-3" />
            </Link>
          </div>
        </div>
      ) : (
        <span className="text-caption text-ink-muted">Your store</span>
      )}
      <Button asChild variant="primary" size="sm" className="w-full">
        <Link href="/seller/products/new">
          <Plus aria-hidden /> Add a product
        </Link>
      </Button>
    </div>
  );
}
