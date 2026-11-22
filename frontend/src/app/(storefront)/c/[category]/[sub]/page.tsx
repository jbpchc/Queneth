import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ListingPage } from "@/components/catalog/listing/listing-page";
import { getCategory } from "@/lib/catalog";
import type { SearchParams } from "@/lib/listing-params";

interface Props {
  params: Promise<{ category: string; sub: string }>;
  searchParams: Promise<SearchParams>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { category, sub } = await params;
  const c = await getCategory(category);
  const s = c.subcategories.find((x) => x.slug === sub);
  return { title: s ? `${s.name} · ${c.name}` : c.name };
}

export default async function SubcategoryPage({ params, searchParams }: Props) {
  const { category, sub } = await params;
  const c = await getCategory(category);
  const current = c.subcategories.find((s) => s.slug === sub);
  if (!current) notFound();
  return (
    <ListingPage
      searchParams={await searchParams}
      fixed={{ category, subcategory: sub }}
      hide={["subcategory"]}
      header={
        <header className="flex flex-col gap-2">
          <nav aria-label="Breadcrumb" className="text-small text-ink-muted">
            <a href={`/c/${c.slug}`} className="hover:text-ink hover:underline">{c.name}</a>
            <span aria-hidden> / </span>
            <span aria-current="page">{current.name}</span>
          </nav>
          <h1 className="text-h1 text-ink">{current.name}</h1>
        </header>
      }
      subnav={[
        { label: "All", href: `/c/${c.slug}`, active: false, count: c.product_count },
        ...c.subcategories.map((s) => ({ label: s.name, href: `/c/${c.slug}/${s.slug}`, active: s.slug === sub, count: s.product_count })),
      ]}
    />
  );
}
