import type { Metadata } from "next";
import { Suspense } from "react";

import { SellersView } from "./sellers-view";

export const metadata: Metadata = { title: "Sellers", robots: { index: false } };

export default function AdminSellersPage() {
  return (
    <Suspense>
      <SellersView />
    </Suspense>
  );
}
