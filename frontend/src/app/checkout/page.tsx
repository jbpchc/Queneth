import type { Metadata } from "next";

import { CheckoutView } from "./checkout-view";

export const metadata: Metadata = { title: "Checkout", robots: { index: false } };

/** `/checkout` pays for the whole bag; `/checkout?items=<line id>` is "Buy now" for one piece. */
export default async function CheckoutPage({ searchParams }: { searchParams: Promise<{ items?: string | string[] }> }) {
  const { items } = await searchParams;
  const ids = (Array.isArray(items) ? items : items ? items.split(",") : []).filter(Boolean).slice(0, 50);
  return <CheckoutView items={ids} />;
}
