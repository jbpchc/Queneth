import type { Metadata } from "next";

import { CatalogView } from "./catalog-view";

export const metadata: Metadata = { title: "Catalog", robots: { index: false } };

export default function AdminCatalogPage() {
  return <CatalogView />;
}
