import type { Metadata } from "next";

import { InventoryView } from "./inventory-view";

export const metadata: Metadata = { title: "Stock", robots: { index: false } };

export default function InventoryPage() {
  return <InventoryView />;
}
