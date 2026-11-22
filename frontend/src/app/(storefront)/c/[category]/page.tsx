import type { Metadata } from "next";

import { ListingPage } from "@/components/catalog/listing/listing-page";
import { getCategory } from "@/lib/catalog";
import type { SearchParams } from "@/lib/listing-params";

interface Props {
  params: Promise<{ category: string }>;
  searchParams: Promise<SearchParams>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { category } = await params;
  const c = await getCategory(category);
  return { title: c.name, description: `${c.tagline} ${c.product_count} pieces from independent boutiques.` };
}

export default async function CategoryPage({ params, searchParams }: Props) {
  const { category } = await params;
  const c = await getCategory(category);
  return (
    <ListingPage
      searchParams={await searchParams}
      fixed={{ category }}
      hide={["subcategory"]}
      header={
        <header className="flex flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">The house</p>
          <h1 className="text-h1 text-ink">{c.name}</h1>
          {c.tagline && <p className="max-w-measure text-ink-muted">{c.tagline}</p>}
        </header>
      }
      subnav={[
        { label: "All", href: `/c/${c.slug}`, active: true, count: c.product_count },
        ...c.subcategories.map((s) => ({ label: s.name, href: `/c/${c.slug}/${s.slug}`, active: false, count: s.product_count })),
      ]}
    />
  );
}
