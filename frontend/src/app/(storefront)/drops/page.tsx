import { Sparkles } from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { Countdown } from "@/components/catalog/countdown";
import { NotifyToggle } from "@/components/catalog/notify-toggle";
import { ProductGrid } from "@/components/catalog/product-card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/states";
import { getDrops, type Drop } from "@/lib/catalog";

export const metadata: Metadata = {
  title: "Queneth Drops",
  description: "Scheduled releases from independent boutiques. Real countdowns, limited pieces, no fake urgency.",
};

export const dynamic = "force-dynamic";

const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Manila" });

export default async function DropsPage() {
  const drops = await getDrops();
  const live = drops.filter((d) => d.status === "live");
  const upcoming = drops.filter((d) => d.status === "upcoming");
  return (
    <div className="mx-auto flex max-w-[1536px] flex-col gap-16 px-4 pb-16 pt-8 sm:px-6 md:pt-12 lg:px-10">
      <header className="flex max-w-3xl flex-col gap-3">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Anticipation, honestly</p>
        <h1 className="text-h1 text-ink">Queneth Drops</h1>
        <p className="max-w-measure text-ink-muted">
          Boutiques schedule small releases here. Every countdown is the real release time, and pieces stay hidden
          until the moment they go live.
        </p>
      </header>

      {drops.length === 0 && (
        <EmptyState icon={Sparkles} title="No drops scheduled" description="Follow a few boutiques; their next release will show up here." action={<Link href="/boutiques" className="font-semibold text-accent-2 underline">Browse boutiques</Link>} />
      )}

      {live.map((d) => (
        <section key={d.slug} id={d.slug} aria-labelledby={`${d.slug}-title`} className="scroll-mt-28 flex flex-col gap-8">
          <DropHeader drop={d} />
          <ProductGrid cards={d.products} />
        </section>
      ))}

      {upcoming.length > 0 && (
        <section aria-labelledby="upcoming" className="flex flex-col gap-6">
          <h2 id="upcoming" className="text-h2 text-ink">Coming soon</h2>
          <ul className="grid gap-6 lg:grid-cols-2">
            {upcoming.map((d) => (
              <li key={d.slug} id={d.slug} className="scroll-mt-28 overflow-hidden rounded-card bg-ink text-bg">
                {d.hero_url && (
                  <div className="relative h-44">
                    <Image src={d.hero_url} alt="" fill sizes="(min-width: 1280px) 50vw, 100vw" className="object-cover opacity-90" />
                  </div>
                )}
                <div className="flex flex-col gap-4 p-8">
                  <p className="text-caption font-bold uppercase tracking-[0.14em] opacity-70">
                    {d.boutique.name} · {d.product_count} pieces · {dateFmt.format(new Date(d.starts_at))}
                  </p>
                  <h3 className="text-h2">{d.title}</h3>
                  <p className="max-w-measure opacity-80">{d.description}</p>
                  <Countdown to={d.starts_at} />
                  <NotifyToggle slug={d.slug} title={d.title} initial={d.is_subscribed} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function DropHeader({ drop }: { drop: Drop }) {
  return (
    <div className="grain relative grid overflow-hidden rounded-card border border-border bg-surface-muted md:grid-cols-2">
      <div className="relative z-[2] flex flex-col gap-4 p-8 md:p-12">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="citrus" withIcon={false}>Live now</Badge>
          <Link href={`/b/${drop.boutique.slug}`} className="text-small text-ink-muted hover:text-ink hover:underline">{drop.boutique.name}</Link>
        </div>
        <h2 id={`${drop.slug}-title`} className="text-display text-ink">{drop.title}</h2>
        <p className="max-w-measure text-ink-muted">{drop.description}</p>
        {drop.ends_at && (
          <div className="flex flex-col gap-1 text-ink">
            <span className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Closes in</span>
            <Countdown to={drop.ends_at} />
          </div>
        )}
      </div>
      {drop.hero_url && (
        <div className="relative min-h-56">
          <Image src={drop.hero_url} alt="" fill sizes="(min-width: 768px) 50vw, 100vw" className="object-cover" />
        </div>
      )}
    </div>
  );
}
