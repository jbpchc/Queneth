import Image from "next/image";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Price } from "@/components/ui/price";
import type { ApiSchemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

import { WishlistHeart } from "./wishlist-heart";

type Card = ApiSchemas["ProductCard"];

/** Badges render only when true (spec §6 guardrails: no fake scarcity). */
export function CardBadges({
  badges,
  stock,
  pick,
}: {
  badges: Card["badges"];
  stock: number;
  pick?: boolean;
}) {
  const b = new Set(badges);
  return (
    <div className="pointer-events-none absolute left-2.5 top-2.5 flex flex-col items-start gap-1.5">
      {b.has("new_drop") && <Badge tone="citrus" withIcon={false}>New drop</Badge>}
      {b.has("low_stock") && (
        // UX: Von Restorff effect — citrus only for true, rare signals.
        <Badge tone="citrus" withIcon={false}>
          Last {stock} left
        </Badge>
      )}
      {b.has("sold_out") && <Badge tone="ink" withIcon={false}>Sold out</Badge>}
      {b.has("sale") && <Badge tone="tangerine" withIcon={false}>Markdown</Badge>}
      {pick && <Badge tone="ink" withIcon={false}>Connoisseur&apos;s pick</Badge>}
      {b.has("preloved") && <Badge withIcon={false}>Pre-loved</Badge>}
    </div>
  );
}

/**
 * UX: Prägnanz — image, brand, name, price and the heart. Nothing else until
 * hover, when the second image cross-fades in and the card lifts.
 */
export function ProductCard({
  card,
  pick = false,
  priority = false,
  sizes = "(min-width: 1280px) 22vw, (min-width: 768px) 31vw, 46vw",
  className,
}: {
  card: Card;
  pick?: boolean;
  priority?: boolean;
  sizes?: string;
  className?: string;
}) {
  return (
    <article className={cn("group relative flex flex-col gap-3", className)}>
      <Link
        href={`/p/${card.slug}`}
        className="relative block aspect-[4/5] overflow-hidden rounded-card bg-surface-muted transition-[box-shadow,transform] duration-[var(--dur-fast)] ease-brand group-hover:shadow-2 motion-safe:group-hover:-translate-y-1"
        prefetch
      >
        {card.image && (
          <Image
            src={card.image.url}
            alt={card.image.alt}
            fill
            sizes={sizes}
            priority={priority}
            className={cn(
              "object-cover transition-opacity duration-[var(--dur-base)] ease-brand",
              card.hover_image && "group-hover:opacity-0",
              card.total_stock === 0 && "opacity-60",
            )}
          />
        )}
        {card.hover_image && (
          <Image
            src={card.hover_image.url}
            alt=""
            aria-hidden
            fill
            sizes={sizes}
            className="object-cover opacity-0 transition-opacity duration-[var(--dur-base)] ease-brand group-hover:opacity-100"
          />
        )}
        <CardBadges badges={card.badges} stock={card.total_stock} pick={pick} />
        <span className="sr-only">View {card.title}</span>
      </Link>
      <WishlistHeart productId={card.id} title={card.title} className="absolute right-2.5 top-2.5" />
      <div className="flex flex-col gap-0.5">
        <p className="truncate text-caption font-bold uppercase tracking-[0.1em] text-ink-muted">{card.brand.name}</p>
        <h3 className="line-clamp-2 font-sans text-small font-semibold leading-snug text-ink">
          <Link href={`/p/${card.slug}`} className="hover:underline hover:underline-offset-4">
            {card.title}
          </Link>
        </h3>
        <Price amount={card.price_qc} compareAt={card.compare_at_qc} size="sm" />
        {card.colors.length > 1 && (
          <ul aria-label={`${card.colors.length} colors`} className="mt-1 flex gap-1">
            {card.colors.slice(0, 5).map((c) => (
              <li
                key={c.name}
                title={c.name}
                className="size-3 rounded-full border border-border-strong/40"
                style={{ background: c.hex ?? undefined }}
              />
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}

export function ProductGrid({
  cards,
  pickId,
  className,
}: {
  cards: Card[];
  pickId?: string | null;
  className?: string;
}) {
  return (
    <ul className={cn("grid grid-cols-2 gap-x-4 gap-y-10 sm:grid-cols-3 lg:grid-cols-4", className)}>
      {cards.map((card, i) => (
        <li key={card.id}>
          <ProductCard card={card} pick={card.id === pickId} priority={i < 4} />
        </li>
      ))}
    </ul>
  );
}
