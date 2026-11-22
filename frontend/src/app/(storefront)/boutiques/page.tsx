import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { FollowButton } from "@/components/catalog/follow-button";
import { getBoutiques } from "@/lib/catalog";
import { formatNumber } from "@/lib/format";

export const metadata: Metadata = {
  title: "Boutiques",
  description: "The independent boutiques of Queneth: ateliers, perfumers, shoemakers and jewelers.",
};

export default async function BoutiquesPage() {
  const boutiques = await getBoutiques();
  return (
    <div className="mx-auto flex max-w-[1536px] flex-col gap-10 px-4 pb-16 pt-8 sm:px-6 md:pt-12 lg:px-10">
      <header className="flex max-w-3xl flex-col gap-3">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Independent houses</p>
        <h1 className="text-h1 text-ink">Boutiques</h1>
        <p className="max-w-measure text-ink-muted">
          Every boutique on Queneth is reviewed and approved by our team. Follow the ones you love to see their new
          pieces first.
        </p>
      </header>
      <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {boutiques.map((b) => (
          <li
            key={b.slug}
            className="flex flex-col overflow-hidden rounded-card border border-border bg-surface shadow-1 transition-shadow hover:shadow-2"
          >
            <Link href={`/b/${b.slug}`} className="relative block h-36" aria-label={`${b.name} storefront`}>
              {b.banner_url && (
                <Image src={b.banner_url} alt="" fill sizes="(min-width: 1280px) 33vw, (min-width: 768px) 50vw, 100vw" className="object-cover" />
              )}
            </Link>
            <div className="flex flex-1 flex-col gap-3 p-6">
              {b.logo_url && (
                <Image src={b.logo_url} alt="" width={72} height={72} className="-mt-14 rounded-full border-4 border-surface bg-surface" />
              )}
              <div>
                <h2 className="text-h3 text-ink">
                  <Link href={`/b/${b.slug}`} className="hover:underline hover:underline-offset-4">
                    {b.name}
                  </Link>
                </h2>
                <p className="text-small text-ink-muted">{b.tagline}</p>
              </div>
              <p className="tabular text-caption text-ink-muted">
                {b.city} · {b.product_count} pieces · {formatNumber(b.follower_count)} followers
              </p>
              <div className="mt-auto pt-2">
                <FollowButton slug={b.slug} name={b.name} initialFollowing={b.is_following} initialCount={b.follower_count} />
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
