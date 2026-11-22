import type { Metadata } from "next";

import { ProductRail } from "@/components/catalog/product-rail";
import { getHome } from "@/lib/catalog";

import { SuccessView } from "./success-view";

export const metadata: Metadata = { title: "Order confirmed", robots: { index: false } };

export default async function CheckoutSuccessPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // The rail is a nice-to-have: the confirmation must render even if it fails.
  const home = await getHome().catch(() => null);
  return (
    <div className="flex flex-col gap-16">
      <SuccessView id={id} />
      {home && (
        <ProductRail
          title="Keep exploring"
          kicker="Trending now"
          href="/search?sort=most_wished"
          cards={home.trending.slice(0, 10)}
          className="-mx-4 sm:-mx-6"
        />
      )}
    </div>
  );
}
