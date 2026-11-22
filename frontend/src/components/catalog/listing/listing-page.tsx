import Link from "next/link";
import type { ReactNode } from "react";

import { getListing } from "@/lib/catalog";
import { toApiQuery, type SearchParams } from "@/lib/listing-params";
import { cn } from "@/lib/utils";

import { FilterBar } from "./filter-bar";
import { ListingResults } from "./listing-results";

interface ListingPageProps {
  searchParams: SearchParams;
  /** Params fixed by the route, e.g. {category: "perfumes"} or {boutique: "obra-leather"}. */
  fixed?: Record<string, string>;
  header?: ReactNode;
  subnav?: { label: string; href: string; active: boolean; count?: number }[];
  hide?: ("boutique" | "subcategory")[];
  emptyTitle?: string;
  emptyHint?: string;
}

/** Shared listing: categories, subcategories, search, boutiques, collections. */
export async function ListingPage({ searchParams, fixed = {}, header, subnav, hide, emptyTitle, emptyHint }: ListingPageProps) {
  const query = toApiQuery(searchParams, fixed);
  const { listing, corrected } = await getListing({ ...query, limit: "24" });
  const key = JSON.stringify(query);

  return (
    <div className="mx-auto flex max-w-[1536px] flex-col gap-6 px-4 pb-16 pt-8 sm:px-6 md:pt-12 lg:px-10">
      {header}
      {subnav && subnav.length > 0 && (
        <nav aria-label="Subcategories" className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <ul className="flex gap-2">
            {subnav.map((s) => (
              <li key={s.href} className="shrink-0">
                <Link
                  href={s.href}
                  aria-current={s.active ? "page" : undefined}
                  className={cn(
                    "inline-flex h-11 items-center gap-1.5 rounded-pill border px-4 text-small font-semibold transition-colors",
                    s.active ? "border-ink bg-ink text-bg" : "border-border-strong text-ink hover:border-ink",
                  )}
                >
                  {s.label}
                  {s.count !== undefined && <span className="tabular opacity-70">{s.count}</span>}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
      {corrected && listing && listing.total > 0 && (
        <p className="text-small text-ink-muted" role="status">
          Showing results for <strong className="text-ink">“{corrected}”</strong>.
        </p>
      )}
      {listing ? (
        <FilterBar facets={listing.facets} total={listing.total} category={fixed.category} hide={hide}>
          <ListingResults key={key} initial={listing} query={{ ...query, limit: "24" }} emptyTitle={emptyTitle} emptyHint={emptyHint} />
        </FilterBar>
      ) : (
        <p role="alert" className="rounded-card border border-warning/30 bg-warning-soft p-4 text-small">
          Some filters in this link aren&apos;t valid. <Link href="?" className="font-semibold underline">Start over</Link>
        </p>
      )}
    </div>
  );
}
