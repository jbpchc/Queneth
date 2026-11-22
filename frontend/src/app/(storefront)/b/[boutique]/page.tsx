import { BadgeCheck, MapPin, Star } from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";

import { FollowButton } from "@/components/catalog/follow-button";
import { ProductCard } from "@/components/catalog/product-card";
import { ListingPage } from "@/components/catalog/listing/listing-page";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/tabs";
import { getBoutique } from "@/lib/catalog";
import type { SearchParams } from "@/lib/listing-params";

interface Props {
  params: Promise<{ boutique: string }>;
  searchParams: Promise<SearchParams>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const b = await getBoutique((await params).boutique);
  return {
    title: b.name,
    description: b.tagline ?? undefined,
    openGraph: { images: b.banner_url ? [{ url: b.banner_url }] : [] },
  };
}

export default async function BoutiquePage({ params, searchParams }: Props) {
  const { boutique } = await params;
  const b = await getBoutique(boutique);
  return (
    <>
      <section className="relative h-48 md:h-72" aria-hidden>
        {b.banner_url && <Image src={b.banner_url} alt="" fill priority sizes="100vw" className="object-cover" />}
      </section>
      <ListingPage
        searchParams={await searchParams}
        fixed={{ boutique: b.slug }}
        hide={["boutique"]}
        emptyTitle={`${b.name} is restocking`}
        emptyHint="Follow the boutique and its new pieces will appear on your home page."
        header={
          <>
          <header className="-mt-20 grid gap-8 md:-mt-24 md:grid-cols-[1fr_340px]">
            <div className="flex flex-col gap-4">
              {b.logo_url && (
                <Image src={b.logo_url} alt={`${b.name} logo`} width={112} height={112} className="rounded-full border-4 border-bg bg-bg shadow-2" />
              )}
              <div className="flex flex-col gap-2">
                <h1 className="text-h1 text-ink">{b.name}</h1>
                {b.tagline && <p className="font-display text-h3 italic text-ink">{b.tagline}</p>}
                <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-small text-ink-muted">
                  <span className="inline-flex items-center gap-1">
                    <MapPin aria-hidden className="size-4" /> {b.city}
                  </span>
                  {b.rating_count > 0 && (
                    <span className="inline-flex items-center gap-1">
                      <Star aria-hidden className="size-4 fill-ink text-ink" /> {b.rating_avg.toFixed(1)} from {b.rating_count} reviews
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1 text-success">
                    <BadgeCheck aria-hidden className="size-4" /> Approved boutique
                  </span>
                </p>
              </div>
              {b.bio && <p className="max-w-measure text-ink-muted">{b.bio}</p>}
              <FollowButton slug={b.slug} name={b.name} initialFollowing={b.is_following} initialCount={b.follower_count} showCount size="md" />
            </div>
            <aside className="self-end">
              <Accordion type="single" collapsible className="rounded-card border border-border bg-surface px-5">
                <AccordionItem value="returns" className="border-b-0">
                  <AccordionTrigger>Returns policy</AccordionTrigger>
                  <AccordionContent>{b.return_policy}</AccordionContent>
                </AccordionItem>
              </Accordion>
            </aside>
          </header>
          {b.featured.length > 0 && (
            <section aria-labelledby="featured-heading" className="mt-10 flex flex-col gap-4">
              <h2 id="featured-heading" className="text-h3 text-ink">Featured by {b.name}</h2>
              <ul className="grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-4">
                {b.featured.map((card) => <li key={card.id}><ProductCard card={card} /></li>)}
              </ul>
            </section>
          )}
          {b.lookbook.length > 0 && (
            <section aria-labelledby="lookbook-heading" className="mt-10 flex flex-col gap-4">
              <h2 id="lookbook-heading" className="text-h3 text-ink">Lookbook</h2>
              <ul className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2">
                {b.lookbook.map((img) => (
                  <li key={img.url} className="w-64 shrink-0 snap-start">
                    <figure className="flex flex-col gap-2">
                      <div className="relative aspect-[4/5] overflow-clip rounded-card bg-surface-muted">
                        <Image src={img.url} alt={img.alt} fill sizes="256px" className="object-cover" />
                      </div>
                      <figcaption className="text-small text-ink-muted">{img.alt}</figcaption>
                    </figure>
                  </li>
                ))}
              </ul>
            </section>
          )}
          </>
        }
      />
    </>
  );
}
