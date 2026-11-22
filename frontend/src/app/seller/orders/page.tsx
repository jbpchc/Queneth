import type { Metadata } from "next";

import { SellerOrders } from "./seller-orders";

export const metadata: Metadata = { title: "Orders", robots: { index: false } };

export default function SellerOrdersPage() {
  return <SellerOrders />;
}
