import type { Metadata } from "next";
import Image from "next/image";

import { ListingPage } from "@/components/catalog/listing/listing-page";
import { getCollection } from "@/lib/catalog";
import type { SearchParams } from "@/lib/listing-params";

interface Props {
  params: Promise<{ slug: string }>;
  searchParams: Promise<SearchParams>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const c = await getCollection((await params).slug);
  return { title: c.title, description: c.subtitle ?? undefined };
}

export default async function CollectionPage({ params, searchParams }: Props) {
  const c = await getCollection((await params).slug);
  return (
    <>
      {/* Editorial header: oversized serif over the hero (asymmetric marketing surface). */}
      <section className="grain relative overflow-hidden border-b border-border">
        {c.hero_url && <Image src={c.hero_url} alt="" fill priority sizes="100vw" className="object-cover opacity-60" />}
        <div className="relative z-[2] mx-auto flex max-w-[1536px] flex-col gap-4 px-4 py-16 sm:px-6 md:py-24 lg:px-10">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink">{c.kicker}</p>
          <h1 className="max-w-4xl text-display text-ink">{c.title}</h1>
          {c.subtitle && <p className="max-w-2xl font-display text-h3 italic text-ink">{c.subtitle}</p>}
          {c.body && <p className="max-w-measure text-ink">{c.body}</p>}
        </div>
      </section>
      <ListingPage searchParams={await searchParams} fixed={{ tag: c.tag }} />
    </>
  );
}
