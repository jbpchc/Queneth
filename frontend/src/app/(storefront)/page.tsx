import { ArrowRight, Store } from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { Countdown } from "@/components/catalog/countdown";
import { FollowButton } from "@/components/catalog/follow-button";
import { GuestWelcome } from "@/components/catalog/guest-welcome";
import { NotifyToggle } from "@/components/catalog/notify-toggle";
import { ProductCard } from "@/components/catalog/product-card";
import { ProductRail } from "@/components/catalog/product-rail";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { getDeals, getHome, type Category, type Deals, type HomeData } from "@/lib/catalog";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: { absolute: "Queneth — Curated for the connoisseur" },
  description:
    "Independent boutiques, authenticated pieces and niche perfumery. Clothing, shoes, bags, accessories and fragrance, curated for the connoisseur.",
};

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [home, deals] = await Promise.all([getHome(), getDeals()]);
  // Everything below comes from boutiques' own listings: with none yet, the
  // page says so instead of showing placeholder merchandise.
  const pieces = home.categories.reduce((n, c) => n + c.product_count, 0);
  if (pieces === 0) return <OpeningSoon categories={home.categories} />;
  return (
    <div className="flex flex-col gap-20 pb-8 md:gap-28">
      <Hero home={home} />
      <GuestWelcome />
      <DealsSection deals={deals} />
      <CategoryBento categories={home.categories} />
      <ProductRail kicker="Curated for you" title="Chosen this week" href="/search?sort=curated" cards={home.curated} />
      {home.editorial && <EditorialBand collection={home.editorial} />}
      <ProductRail kicker="Most wished" title="Trending now" href="/search?sort=most_wished" cards={home.trending} />
      {home.upcoming_drop && <UpcomingDrop drop={home.upcoming_drop} />}
      <ProductRail kicker="Just in" title="New arrivals" href="/search?sort=newest" cards={home.new_arrivals} />
      <FeaturedBoutiques boutiques={home.featured_boutiques} />
    </div>
  );
}

function Hero({ home }: { home: HomeData }) {
  const drop = home.live_drop;
  // Collage: the live drop's pieces, else the top piece from each category.
  const images = drop
    ? drop.products.flatMap((p) => (p.image ? [p.image] : [])).slice(0, 3)
    : home.categories.flatMap((c) => (c.cover_url ? [{ url: c.cover_url, alt: "" }] : [])).slice(0, 3);
  return (
    <section className="grain overflow-hidden border-b border-border">
      <div className="relative z-[2] mx-auto grid max-w-[1536px] items-center gap-10 px-4 pb-14 pt-10 sm:px-6 md:grid-cols-12 md:pb-20 md:pt-16 lg:px-10">
        <div className="flex flex-col gap-6 md:col-span-6">
          {drop ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="citrus" withIcon={false}>Live drop</Badge>
                <span className="text-small text-ink-muted">by {drop.boutique.name}</span>
              </div>
              <h1 className="text-display text-ink">{drop.title}</h1>
              <p className="max-w-measure text-h3 font-sans font-normal leading-snug text-ink-muted">{drop.description}</p>
              <div className="flex flex-wrap items-center gap-4">
                {/* UX: Von Restorff effect — the single accent CTA on the home page. */}
                <Button asChild variant="primary" size="lg">
                  <Link href={`/drops#${drop.slug}`}>
                    Shop the drop <ArrowRight aria-hidden />
                  </Link>
                </Button>
                {drop.ends_at && (
                  <div className="flex flex-col gap-1 text-ink">
                    <span className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Closes in</span>
                    <Countdown to={drop.ends_at} />
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">
                {home.categories.reduce((n, c) => n + c.product_count, 0)} pieces from independent boutiques
              </p>
              <h1 className="text-display text-ink">
                Curated for the <em className="italic text-accent">connoisseur.</em>
              </h1>
              <Button asChild variant="primary" size="lg" className="self-start">
                <Link href="/search?sort=newest">Explore new arrivals</Link>
              </Button>
            </>
          )}
        </div>
        {/* Overlapping editorial collage (asymmetric marketing surface, spec §4). */}
        <div className="relative h-[420px] md:col-span-6 md:h-[560px]" aria-hidden={images.length === 0}>
          {images.map((img, i) => (
            <div
              key={img.url}
              className={cn(
                "absolute overflow-hidden rounded-card shadow-3",
                i === 0 && "left-[6%] top-0 z-[2] h-[78%] w-[52%]",
                i === 1 && "right-0 top-[12%] z-[1] h-[64%] w-[42%]",
                i === 2 && "bottom-0 left-[38%] z-[3] h-[44%] w-[34%]",
              )}
            >
              <Image src={img.url} alt={img.alt} fill priority={i === 0} sizes="(min-width: 768px) 28vw, 50vw" className="object-cover" />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CategoryBento({ categories }: { categories: Category[] }) {
  // Asymmetric bento: the first tile spans two rows on desktop.
  const layout = [
    "md:col-span-2 md:row-span-2",
    "md:col-span-1",
    "md:col-span-1",
    "md:col-span-1",
    "md:col-span-1",
  ];
  return (
    <section aria-labelledby="shop-by" className="mx-auto w-full max-w-[1536px] px-4 sm:px-6 lg:px-10">
      <div className="mb-6 flex flex-col gap-1">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">The house</p>
        <h2 id="shop-by" className="text-h2 text-ink">Shop by category</h2>
      </div>
      <ul className="grid auto-rows-[200px] grid-cols-2 gap-4 md:auto-rows-[240px] md:grid-cols-4">
        {categories.map((c, i) => (
          <li key={c.slug} className={cn(layout[i], i === 0 && "col-span-2 row-span-2")}>
            <Link
              href={`/c/${c.slug}`}
              className={cn(
                "group relative flex h-full flex-col justify-end overflow-hidden rounded-card p-5 shadow-1 transition-shadow hover:shadow-2",
                c.cover_url ? "bg-surface-muted" : "bg-ink",
              )}
            >
              {/* Cover = the most-wished in-stock piece boutiques have tagged into this
                  category; the large tile shows a mosaic from up to four boutiques. */}
              <CategoryCover category={c} large={i === 0} />
              <span className="absolute inset-0 bg-gradient-to-t from-[rgb(20_18_20/0.55)] via-transparent to-transparent" />
              <span className="relative z-[1] flex items-end justify-between gap-3 text-[#faf7f2]">
                <span className="flex flex-col">
                  <span className={cn("font-display", i === 0 ? "text-h1" : "text-h3")}>{c.name}</span>
                  {i === 0 && c.tagline && <span className="text-small opacity-90">{c.tagline}</span>}
                </span>
                <span className="tabular text-caption font-semibold opacity-90">
                  {c.product_count > 0 ? `${c.product_count} ${c.product_count === 1 ? "piece" : "pieces"}` : "Coming soon"}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function CategoryCover({ category: c, large }: { category: Category; large: boolean }) {
  const sizes = large ? "(min-width: 768px) 50vw, 100vw" : "(min-width: 768px) 25vw, 50vw";
  const zoom =
    "object-cover transition-transform duration-[var(--dur-base)] ease-brand motion-safe:group-hover:scale-[1.03]";
  if (large && c.cover_images.length >= 4) {
    return (
      <span className="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-0.5">
        {c.cover_images.slice(0, 4).map((url) => (
          <span key={url} className="relative overflow-hidden">
            <Image src={url} alt="" fill sizes="(min-width: 768px) 25vw, 50vw" className={zoom} />
          </span>
        ))}
      </span>
    );
  }
  // No tagged pieces yet: a quiet textured tile instead of stock imagery.
  if (!c.cover_url) return <span aria-hidden className="grain absolute inset-0 opacity-60" />;
  return <Image src={c.cover_url} alt="" fill sizes={sizes} className={zoom} />;
}

/** Live platform sales and pieces boutiques have marked down. Hidden when nothing is on sale. */
function DealsSection({ deals }: { deals: Deals }) {
  if (!deals.promotions.length && !deals.on_sale.length) return null;
  return (
    <div className="flex flex-col gap-10">
      {deals.promotions.slice(0, 2).map((p) => (
        <section
          key={p.id}
          aria-labelledby={`promo-${p.slug}`}
          className="mx-auto w-full max-w-[1536px] px-4 sm:px-6 lg:px-10"
        >
          <div className="grid overflow-hidden rounded-card bg-ink text-bg md:grid-cols-12">
            <div className="flex flex-col gap-4 p-8 md:col-span-5 md:p-12">
              <Badge tone="citrus" withIcon={false} className="self-start">
                {p.badge}
              </Badge>
              <h2 id={`promo-${p.slug}`} className="text-h1">
                {p.title}
              </h2>
              {p.description && <p className="max-w-measure opacity-80">{p.description}</p>}
              <p className="text-small font-semibold">
                Up to {p.top_discount_percent}% off · {p.seller_count}{" "}
                {p.seller_count === 1 ? "boutique" : "boutiques"}
              </p>
              <div className="flex flex-wrap items-center gap-4">
                {/* UX: Von Restorff effect — one accent CTA per sale banner. */}
                <Button asChild variant="primary" size="lg">
                  <Link href={`/deals/${p.slug}`}>
                    Shop the sale <ArrowRight aria-hidden />
                  </Link>
                </Button>
                <div className="flex flex-col gap-1">
                  <span className="text-caption font-bold uppercase tracking-[0.14em] opacity-70">Ends in</span>
                  <Countdown to={p.ends_at} />
                </div>
              </div>
            </div>
            <ul className="grid grid-cols-2 gap-0.5 md:col-span-7 md:grid-cols-4">
              {p.preview.slice(0, 4).map((card) => (
                <li key={card.id} className="relative aspect-[4/5] md:aspect-auto">
                  <Link href={`/p/${card.slug}`} aria-label={card.title} className="absolute inset-0">
                    {card.image && (
                      <Image
                        src={card.image.url}
                        alt={card.image.alt}
                        fill
                        sizes="(min-width: 768px) 15vw, 50vw"
                        className="object-cover"
                      />
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ))}
      <ProductRail
        kicker="Marked down by our boutiques"
        title="On sale now"
        href="/deals"
        cards={deals.on_sale.slice(0, 12)}
      />
    </div>
  );
}

/** A marketplace with no listings yet: an honest empty state, not placeholder stock. */
function OpeningSoon({ categories }: { categories: Category[] }) {
  return (
    <div className="mx-auto flex w-full max-w-[1536px] flex-col gap-12 px-4 py-16 sm:px-6 md:py-24 lg:px-10">
      <EmptyState
        icon={Store}
        title="Our boutiques are setting up"
        description="Queneth is a marketplace of independent boutiques. Pieces appear here as soon as a boutique publishes them."
        action={
          <div className="flex flex-wrap justify-center gap-3">
            <Button asChild variant="primary">
              <Link href="/account/sell">Sell on Queneth</Link>
            </Button>
            <Button asChild variant="secondary">
              <Link href="/boutiques">See boutiques</Link>
            </Button>
          </div>
        }
      />
      {categories.length > 0 && (
        <section aria-labelledby="coming" className="flex flex-col gap-4">
          <h2 id="coming" className="text-h3 text-ink">
            What boutiques can list
          </h2>
          <ul className="flex flex-wrap gap-2">
            {categories.map((c) => (
              <li key={c.slug}>
                <Link
                  href={`/c/${c.slug}`}
                  className="inline-flex min-h-11 items-center rounded-pill border border-border-strong px-4 text-small font-semibold text-ink hover:bg-surface-muted"
                >
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function EditorialBand({ collection }: { collection: NonNullable<HomeData["editorial"]> }) {
  return (
    <section aria-labelledby="editorial-title" className="bg-surface-muted py-16 md:py-24">
      <div className="mx-auto grid max-w-[1536px] gap-10 px-4 sm:px-6 md:grid-cols-12 lg:px-10">
        <div className="flex flex-col gap-5 md:col-span-4 md:sticky md:top-28 md:self-start">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">{collection.kicker}</p>
          <h2 id="editorial-title" className="text-h1 text-ink">{collection.title}</h2>
          <p className="font-display text-h3 italic text-ink">{collection.subtitle}</p>
          <p className="max-w-measure text-ink-muted">{collection.body}</p>
          <Link
            href={`/collections/${collection.slug}`}
            className="inline-flex min-h-11 items-center gap-1.5 self-start text-small font-semibold text-accent-2 hover:underline hover:underline-offset-4"
          >
            Read the edit · {collection.product_count} pieces <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-10 md:col-span-8 md:grid-cols-3">
          {collection.preview.map((card) => (
            <li key={card.id}>
              <ProductCard card={card} sizes="(min-width: 768px) 20vw, 46vw" />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function UpcomingDrop({ drop }: { drop: NonNullable<HomeData["upcoming_drop"]> }) {
  return (
    // Drops are woven into the editorial flow, never styled as ads (Selective Attention).
    <section aria-labelledby="upcoming-title" className="mx-auto w-full max-w-[1536px] px-4 sm:px-6 lg:px-10">
      <div className="relative grid overflow-hidden rounded-card bg-ink text-bg md:grid-cols-2">
        <div className="relative z-[1] flex flex-col gap-5 p-8 md:p-12">
          <p className="text-caption font-bold uppercase tracking-[0.14em] opacity-70">
            Coming soon · {drop.boutique.name}
          </p>
          <h2 id="upcoming-title" className="text-h1">{drop.title}</h2>
          <p className="max-w-measure opacity-80">{drop.description}</p>
          <Countdown to={drop.starts_at} />
          <NotifyToggle slug={drop.slug} title={drop.title} initial={drop.is_subscribed} />
        </div>
        {drop.hero_url && (
          <div className="relative min-h-56">
            <Image src={drop.hero_url} alt="" fill sizes="(min-width: 768px) 50vw, 100vw" className="object-cover opacity-90" />
          </div>
        )}
      </div>
    </section>
  );
}

function FeaturedBoutiques({ boutiques }: { boutiques: HomeData["featured_boutiques"] }) {
  if (!boutiques.length) return null;
  return (
    <section aria-labelledby="boutiques-title" className="mx-auto w-full max-w-[1536px] px-4 sm:px-6 lg:px-10">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Independent houses</p>
          <h2 id="boutiques-title" className="text-h2 text-ink">Featured boutiques</h2>
        </div>
        <Link href="/boutiques" className="inline-flex min-h-11 items-center gap-1.5 text-small font-semibold text-accent-2 hover:underline">
          All boutiques <ArrowRight aria-hidden className="size-4" />
        </Link>
      </div>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {boutiques.slice(0, 4).map((b) => (
          <li key={b.slug} className="flex flex-col overflow-hidden rounded-card border border-border bg-surface shadow-1">
            <Link href={`/b/${b.slug}`} className="relative block h-28">
              {b.banner_url && <Image src={b.banner_url} alt="" fill sizes="(min-width: 1024px) 25vw, 50vw" className="object-cover" />}
            </Link>
            <div className="flex flex-1 flex-col gap-3 p-5">
              <div className="-mt-12 flex items-end gap-3">
                {b.logo_url && (
                  <Image src={b.logo_url} alt="" width={64} height={64} className="rounded-full border-4 border-surface bg-surface" />
                )}
              </div>
              <div>
                <h3 className="text-h3 text-ink">
                  <Link href={`/b/${b.slug}`} className="hover:underline hover:underline-offset-4">{b.name}</Link>
                </h3>
                <p className="text-small text-ink-muted">{b.tagline}</p>
                <p className="mt-1 text-caption text-ink-muted">{b.city} · {b.product_count} pieces</p>
              </div>
              <div className="mt-auto">
                <FollowButton slug={b.slug} name={b.name} initialFollowing={b.is_following} initialCount={b.follower_count} />
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
