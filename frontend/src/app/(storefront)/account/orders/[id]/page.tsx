import type { Metadata } from "next";

import { OrderDetail } from "./order-detail";

export const metadata: Metadata = { title: "Order", robots: { index: false } };

export default async function OrderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-4xl px-4 pb-16 pt-8 sm:px-6 md:pt-12">
      <OrderDetail id={id} />
    </div>
  );
}
