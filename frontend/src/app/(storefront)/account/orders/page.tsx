import type { Metadata } from "next";
import Link from "next/link";

import { OrdersList } from "./orders-list";

export const metadata: Metadata = { title: "Your orders", robots: { index: false } };

export default function OrdersPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 pb-16 pt-8 sm:px-6 md:pt-12">
      <nav aria-label="Breadcrumb" className="mb-4 text-small text-ink-muted">
        <Link href="/account" className="hover:underline">Account</Link> / Orders
      </nav>
      <h1 className="mb-8 text-h1 text-ink">Your orders</h1>
      <OrdersList />
    </div>
  );
}
