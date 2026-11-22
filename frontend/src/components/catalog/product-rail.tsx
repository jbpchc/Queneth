import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import type { ApiSchemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

import { ProductCard } from "./product-card";

/** Horizontal, snap-scrolling rail. Native scroll keeps it keyboard- and touch-friendly. */
export function ProductRail({
  title,
  kicker,
  href,
  cards,
  className,
  action,
}: {
  title: string;
  kicker?: string;
  href?: string;
  cards: ApiSchemas["ProductCard"][];
  className?: string;
  action?: ReactNode;
}) {
  if (!cards.length) return null;
  const id = `rail-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <section aria-labelledby={id} className={cn("flex flex-col gap-6", className)}>
      <div className="flex items-end justify-between gap-4 px-4 sm:px-6 lg:px-10">
        <div className="flex flex-col gap-1">
          {kicker && <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">{kicker}</p>}
          <h2 id={id} className="text-h2 text-ink">
            {title}
          </h2>
        </div>
        {action ??
          (href && (
            <Link
              href={href}
              className="inline-flex min-h-11 shrink-0 items-center gap-1.5 text-small font-semibold text-accent-2 hover:underline hover:underline-offset-4"
            >
              See all <ArrowRight aria-hidden className="size-4" />
            </Link>
          ))}
      </div>
      <ul className="flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-px-4 px-4 pb-2 [scrollbar-width:thin] sm:scroll-px-6 sm:px-6 lg:scroll-px-10 lg:px-10">
        {cards.map((card) => (
          <li key={card.id} className="w-[46vw] shrink-0 snap-start sm:w-[30vw] md:w-[22vw] xl:w-[17vw]">
            <ProductCard card={card} sizes="(min-width: 1280px) 17vw, (min-width: 768px) 22vw, 46vw" />
          </li>
        ))}
      </ul>
    </section>
  );
}
