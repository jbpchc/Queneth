import type { Metadata } from "next";

import { ListingPage } from "@/components/catalog/listing/listing-page";
import { SearchBox } from "@/components/catalog/search-box";
import { SORTS, asArray, type SearchParams } from "@/lib/listing-params";

interface Props {
  searchParams: Promise<SearchParams>;
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const q = asArray((await searchParams).q)[0];
  return { title: q ? `“${q}”` : "Search", robots: { index: false } };
}

export default async function SearchPage({ searchParams }: Props) {
  const sp = await searchParams;
  const q = asArray(sp.q)[0] ?? "";
  const sort = asArray(sp.sort)[0];
  const sortLabel = SORTS.find((s) => s.value === sort)?.label;
  return (
    <ListingPage
      searchParams={sp}
      emptyTitle={q ? `Nothing for “${q}” yet` : "Nothing matches — yet"}
      emptyHint="Try a broader word (a material, a note, a house), or browse the categories."
      header={
        <header className="flex flex-col gap-5">
          <h1 className="text-h1 text-ink">{q ? <>Results for <em className="italic">“{q}”</em></> : sortLabel && sort !== "curated" ? sortLabel : "Search the house"}</h1>
          <SearchBox key={q} size="page" defaultValue={q} autoFocus={!q} className="max-w-2xl" />
        </header>
      }
    />
  );
}
