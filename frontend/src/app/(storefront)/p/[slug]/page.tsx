import { BadgeCheck, MapPin, ShieldCheck, Truck } from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { FollowButton } from "@/components/catalog/follow-button";
import { CardBadges } from "@/components/catalog/product-card";
import { ProductRail } from "@/components/catalog/product-rail";
import { ReportButton } from "@/components/catalog/report-button";
import { Gallery } from "@/components/product/gallery";
import { CategoryModule } from "@/components/product/modules/category-modules";
import { SizeGuide } from "@/components/product/modules/size-guide";
import { ProductViewProvider } from "@/components/product/product-view";
import { PurchasePanel } from "@/components/product/purchase-panel";
import { Reviews, Stars } from "@/components/product/reviews";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/tabs";
import { getProduct, type ProductDetail } from "@/lib/catalog";
import { env } from "@/lib/env";

interface Props {
  params: Promise<{ slug: string }>;
}

const CONDITION = { new: "New", preloved_excellent: "Pre-loved · Excellent", preloved_good: "Pre-loved · Good" } as Record<string, string>;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const p = await getProduct((await params).slug);
  const description = p.description.split("\n")[0]!.slice(0, 160);
  return {
    title: `${p.title} by ${p.brand.name}`,
    description,
    openGraph: {
      type: "website",
      title: `${p.title} · ${p.brand.name}`,
      description,
      images: p.images.slice(0, 1).map((i) => ({ url: i.url, alt: i.alt })),
    },
    alternates: { canonical: `/p/${p.slug}` },
  };
}

function jsonLd(p: ProductDetail) {
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: p.title,
    description: p.description,
    image: p.images.map((i) => i.url),
    sku: p.variants[0]?.sku,
    brand: { "@type": "Brand", name: p.brand.name },
    itemCondition: p.condition === "new" ? "https://schema.org/NewCondition" : "https://schema.org/UsedCondition",
    ...(p.review_summary.count
      ? { aggregateRating: { "@type": "AggregateRating", ratingValue: p.review_summary.average, reviewCount: p.review_summary.count } }
      : {}),
    offers: {
      "@type": "AggregateOffer",
      // Que Credits are simulated; the PHP figure is a notional 1:1 reference only.
      priceCurrency: "PHP",
      lowPrice: p.price_qc,
      highPrice: p.max_price_qc,
      availability: p.total_stock > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
      url: `${env.siteUrl}/p/${p.slug}`,
    },
  };
}

export default async function ProductPage({ params }: Props) {
  const p = await getProduct((await params).slug);
  const attrs = p.attributes as Record<string, unknown>;
  const firstColor = p.images[0]?.color ?? null;
  const sizeHelp = p.category.slug === "clothing" ? <SizeGuide fit={String(attrs.fit ?? "")} available={p.sizes} /> : null;

  return (
    <ProductViewProvider initialColor={firstColor}>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd(p)).replace(/</g, "\\u003c") }} />
      <div className="mx-auto flex max-w-[1536px] flex-col gap-20 px-4 pb-28 pt-6 sm:px-6 md:gap-24 md:pb-16 md:pt-10 lg:px-10">
        <div className="flex flex-col gap-6">
          <nav aria-label="Breadcrumb" className="text-small text-ink-muted">
            <ol className="flex flex-wrap items-center gap-1.5">
              <li><Link href={`/c/${p.category.slug}`} className="hover:text-ink hover:underline">{p.category.name}</Link></li>
              <li aria-hidden>/</li>
              <li><Link href={`/c/${p.category.slug}/${p.subcategory.slug}`} className="hover:text-ink hover:underline">{p.subcategory.name}</Link></li>
              <li aria-hidden>/</li>
              <li aria-current="page" className="truncate text-ink">{p.title}</li>
            </ol>
          </nav>

          <div className="grid gap-10 md:grid-cols-12 md:gap-12">
            <div className="relative min-w-0 md:col-span-7">
              <Gallery images={p.images} title={p.title} />
              <div className="pointer-events-none md:hidden"><CardBadges badges={p.badges} stock={p.total_stock} /></div>
            </div>
            <div className="flex min-w-0 flex-col gap-8 md:sticky md:top-24 md:col-span-5 md:self-start">
              <header className="flex flex-col gap-3">
                <Link href={`/search?q=${encodeURIComponent(p.brand.name)}`} className="self-start text-caption font-bold uppercase tracking-[0.14em] text-ink-muted hover:text-ink">
                  {p.brand.name}
                </Link>
                <h1 className="text-h1 text-ink">{p.title}</h1>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-small text-ink-muted">
                  {p.review_summary.count > 0 && (
                    <a href="#reviews" className="inline-flex items-center gap-2 hover:text-ink">
                      <Stars value={p.review_summary.average} /> {p.review_summary.count} reviews
                    </a>
                  )}
                  <span>{CONDITION[p.condition] ?? p.condition}</span>
                  {p.drop && <Link href="/drops" className="font-semibold text-ink underline-offset-4 hover:underline">From the drop: {p.drop.title}</Link>}
                </div>
              </header>
              <PurchasePanel product={p} sizeHelp={sizeHelp} />
              <ul className="flex flex-col gap-3 border-t border-border pt-6 text-small text-ink-muted">
                <li className="flex gap-3"><ShieldCheck aria-hidden className="size-5 shrink-0 text-ink" /> {p.authenticity_note}</li>
                <li className="flex gap-3"><Truck aria-hidden className="size-5 shrink-0 text-ink" /> Ships from {p.boutique.city}. Paid with QueWallet and held in escrow until it arrives.</li>
              </ul>
              <ReportButton type="product" id={p.id} />
            </div>
          </div>
        </div>

        <CategoryModule product={p} />

        <section aria-labelledby="details-title" className="grid gap-10 md:grid-cols-12">
          <div className="md:col-span-7">
            <h2 id="details-title" className="mb-4 text-h2 text-ink">The details</h2>
            {/* UX: Miller's Law — details chunked into collapsible groups. */}
            <Accordion type="multiple" defaultValue={["details"]}>
              <AccordionItem value="details">
                <AccordionTrigger>Details</AccordionTrigger>
                <AccordionContent className="flex flex-col gap-3">
                  {p.description.split("\n\n").map((para) => <p key={para} className="max-w-measure">{para}</p>)}
                </AccordionContent>
              </AccordionItem>
              <AccordionItem value="materials">
                <AccordionTrigger>{p.category.slug === "perfumes" ? "Notes" : "Materials and care"}</AccordionTrigger>
                <AccordionContent>
                  <Specs product={p} />
                </AccordionContent>
              </AccordionItem>
              {(p.category.slug === "clothing" || p.category.slug === "shoes") && (
                <AccordionItem value="fit">
                  <AccordionTrigger>Size and fit</AccordionTrigger>
                  <AccordionContent>
                    {p.category.slug === "clothing"
                      ? `${String(attrs.fit)} fit. Model is ${String(attrs.model_height_cm)} cm and wears ${String(attrs.model_size)}.`
                      : `${String(attrs.last)}. Heel height ${String(attrs.heel_height_cm)} cm. Available in EU ${p.sizes[0]}–${p.sizes.at(-1)}.`}
                  </AccordionContent>
                </AccordionItem>
              )}
              <AccordionItem value="shipping">
                <AccordionTrigger>Shipping and returns</AccordionTrigger>
                <AccordionContent className="flex flex-col gap-2">
                  <p>Ships from {p.boutique.city} within 2–4 days with simulated tracking. Your QC is held in escrow and only released to the boutique once you confirm it arrived.</p>
                  <p>Returns within 7 days of delivery for unworn pieces with tags attached.</p>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>
          <aside className="md:col-span-5">
            <BoutiqueCard product={p} />
          </aside>
        </section>

        <div id="reviews" className="scroll-mt-28">
          <Reviews slug={p.slug} summary={p.review_summary} initial={p.reviews} />
        </div>
      </div>

      <div className="mx-auto flex max-w-[1536px] flex-col gap-20 pb-16">
        {p.similar_scents.length > 0 && <ProductRail kicker="Similar scent profiles" title="If you love this, try" cards={p.similar_scents} />}
        <ProductRail kicker="Complete the look" title="Wear it with" cards={p.complete_the_look} />
        <ProductRail kicker="You may also love" title={`More ${p.subcategory.name.toLowerCase()}`} href={`/c/${p.category.slug}/${p.subcategory.slug}`} cards={p.you_may_also_love} />
      </div>
    </ProductViewProvider>
  );
}

function Specs({ product: p }: { product: ProductDetail }) {
  const a = p.attributes as Record<string, unknown>;
  const rows: [string, string][] = [];
  const join = (v: unknown) => (Array.isArray(v) ? v.join(", ") : String(v));
  if (p.category.slug === "clothing") {
    rows.push(["Composition", ((a.composition as { fiber: string; pct: number }[]) ?? []).map((f) => `${f.pct}% ${f.fiber}`).join(", ")]);
    rows.push(["Care", join(a.care)]);
  } else if (p.category.slug === "shoes") {
    rows.push(["Upper", join(a.upper)], ["Lining", join(a.lining)], ["Sole", join(a.sole)]);
  } else if (p.category.slug === "bags") {
    rows.push(["Material", join(a.material)], ["Hardware", join(a.hardware_finish)], ["Interior", join(a.interior)], ["Dimensions", `${a.width_cm} × ${a.height_cm} × ${a.depth_cm} cm`]);
  } else if (p.category.slug === "accessories") {
    rows.push(["Material", join(a.material)]);
    if (a.care) rows.push(["Care", join(a.care)]);
  } else {
    rows.push(["Top", join(a.top_notes)], ["Heart", join(a.heart_notes)], ["Base", join(a.base_notes)], ["Perfumer", join(a.perfumer)]);
  }
  return (
    <dl className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-2 text-small">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-ink-muted">{k}</dt>
          <dd className="text-ink first-letter:uppercase">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function BoutiqueCard({ product: p }: { product: ProductDetail }) {
  const b = p.boutique;
  return (
    <div className="flex flex-col gap-4 rounded-card border border-border bg-surface p-6 shadow-1">
      <div className="flex items-center gap-4">
        {b.logo_url && <Image src={b.logo_url} alt="" width={56} height={56} className="rounded-full" />}
        <div className="flex-1">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Sold by</p>
          <Link href={`/b/${b.slug}`} className="font-display text-h3 text-ink hover:underline hover:underline-offset-4">{b.name}</Link>
          <p className="inline-flex items-center gap-1 text-caption text-ink-muted">
            <MapPin aria-hidden className="size-3.5" /> {b.city} · {b.product_count} pieces
          </p>
        </div>
      </div>
      {b.tagline && <p className="text-small text-ink-muted">{b.tagline}</p>}
      <p className="inline-flex items-center gap-1.5 text-caption text-success">
        <BadgeCheck aria-hidden className="size-4" /> Approved Queneth boutique
      </p>
      <FollowButton slug={b.slug} name={b.name} initialFollowing={b.is_following} initialCount={b.follower_count} showCount />
    </div>
  );
}
