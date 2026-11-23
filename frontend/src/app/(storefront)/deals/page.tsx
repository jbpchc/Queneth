import { ArrowRight, Percent } from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { Countdown } from "@/components/catalog/countdown";
import { ProductCard } from "@/components/catalog/product-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { getDeals } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Deals",
  description: "Live sales and pieces our independent boutiques have marked down.",
};

export const dynamic = "force-dynamic";

/** Every live platform sale, then every genuine markdown, biggest discount first. */
export default async function DealsPage() {
  const deals = await getDeals();
  const empty = !deals.promotions.length && !deals.on_sale.length;
  return (
    <div className="mx-auto flex w-full max-w-[1536px] flex-col gap-14 px-4 py-10 sm:px-6 md:py-14 lg:px-10">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Deals</p>
        <h1 className="text-display text-ink">On sale now</h1>
        <p className="max-w-measure text-ink-muted">
          Every price here is a real markdown set by the boutique: the struck-through price is what the piece sold
          for before.
        </p>
      </header>

      {empty ? (
        <EmptyState
          icon={Percent}
          title="Nothing on sale right now"
          description="Boutiques mark pieces down during platform sales and on their own. Check back soon."
          action={
            <Button asChild variant="secondary">
              <Link href="/search?sort=newest">See new arrivals</Link>
            </Button>
          }
        />
      ) : (
        <>
          {deals.promotions.length > 0 && (
            <ul className="grid gap-4 md:grid-cols-2">
              {deals.promotions.map((p) => (
                <li key={p.id}>
                  <Link
                    href={`/deals/${p.slug}`}
                    className="group relative flex min-h-64 flex-col justify-end gap-3 overflow-hidden rounded-card bg-ink p-6 text-bg shadow-1 transition-shadow hover:shadow-2 md:p-8"
                  >
                    {(p.hero_url ?? p.preview[0]?.image?.url) && (
                      <Image
                        src={(p.hero_url ?? p.preview[0]?.image?.url)!}
                        alt=""
                        fill
                        sizes="(min-width: 768px) 50vw, 100vw"
                        className="object-cover opacity-40 transition-transform duration-[var(--dur-base)] ease-brand motion-safe:group-hover:scale-[1.03]"
                      />
                    )}
                    <span className="relative z-[1] flex flex-col gap-3">
                      <Badge tone="citrus" withIcon={false} className="self-start">
                        {p.badge}
                      </Badge>
                      <span className="text-h1">{p.title}</span>
                      <span className="text-small font-semibold">
                        Up to {p.top_discount_percent}% off · {p.product_count}{" "}
                        {p.product_count === 1 ? "piece" : "pieces"} from {p.seller_count}{" "}
                        {p.seller_count === 1 ? "boutique" : "boutiques"}
                      </span>
                      <span className="flex flex-wrap items-center justify-between gap-3">
                        <Countdown to={p.ends_at} />
                        <span className="inline-flex items-center gap-1.5 text-small font-semibold">
                          Shop the sale <ArrowRight aria-hidden className="size-4" />
                        </span>
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {deals.on_sale.length > 0 && (
            <section aria-labelledby="markdowns" className="flex flex-col gap-6">
              <h2 id="markdowns" className="text-h2 text-ink">
                Biggest markdowns
              </h2>
              <ul className="grid grid-cols-2 gap-x-4 gap-y-10 md:grid-cols-3 lg:grid-cols-4">
                {deals.on_sale.map((card) => (
                  <li key={card.id}>
                    <ProductCard card={card} sizes="(min-width: 1024px) 22vw, (min-width: 768px) 30vw, 46vw" />
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
