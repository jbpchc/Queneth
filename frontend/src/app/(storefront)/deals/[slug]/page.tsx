import { Percent } from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { Countdown } from "@/components/catalog/countdown";
import { ProductCard } from "@/components/catalog/product-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { getPromotion } from "@/lib/catalog";

interface Props {
  params: Promise<{ slug: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const p = await getPromotion((await params).slug);
  return { title: p.title, description: p.description ?? `${p.badge}: up to ${p.top_discount_percent}% off.` };
}

/** One platform sale: every piece boutiques have entered, biggest discount first. */
export default async function PromotionPage({ params }: Props) {
  const p = await getPromotion((await params).slug);
  return (
    <>
      <section className="grain relative overflow-hidden border-b border-border">
        {p.hero_url && <Image src={p.hero_url} alt="" fill priority sizes="100vw" className="object-cover opacity-50" />}
        <div className="relative z-[2] mx-auto flex max-w-[1536px] flex-col gap-4 px-4 py-14 sm:px-6 md:py-20 lg:px-10">
          <Badge tone="citrus" withIcon={false} className="self-start">
            {p.badge}
          </Badge>
          <h1 className="max-w-4xl text-display text-ink">{p.title}</h1>
          {p.description && <p className="max-w-measure text-ink">{p.description}</p>}
          <p className="text-small font-semibold text-ink">
            Up to {p.top_discount_percent}% off · {p.seller_count} {p.seller_count === 1 ? "boutique" : "boutiques"}
          </p>
          <div className="flex flex-col gap-1 text-ink">
            <span className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">
              {p.state === "live" ? "Ends in" : "Starts in"}
            </span>
            <Countdown to={p.state === "live" ? p.ends_at : p.starts_at} />
          </div>
        </div>
      </section>
      <div className="mx-auto w-full max-w-[1536px] px-4 py-10 sm:px-6 lg:px-10">
        {p.products.length === 0 ? (
          <EmptyState
            icon={Percent}
            title={p.state === "live" ? "No pieces in this sale yet" : "This sale hasn't started"}
            description="Boutiques are adding pieces. Prices drop automatically when the sale is live."
            action={
              <Button asChild variant="secondary">
                <Link href="/deals">All deals</Link>
              </Button>
            }
          />
        ) : (
          <ul className="grid grid-cols-2 gap-x-4 gap-y-10 md:grid-cols-3 lg:grid-cols-4">
            {p.products.map((card) => (
              <li key={card.id}>
                <ProductCard card={card} sizes="(min-width: 1024px) 22vw, (min-width: 768px) 30vw, 46vw" />
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
