import type { Metadata } from "next";

import { ProductsView } from "./products-view";

export const metadata: Metadata = { title: "My products", robots: { index: false } };

export default function ProductsPage() {
  return <ProductsView />;
}
