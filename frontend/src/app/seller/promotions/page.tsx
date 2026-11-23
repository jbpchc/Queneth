import type { Metadata } from "next";

import { PromotionsView } from "./promotions-view";

export const metadata: Metadata = { title: "Queneth sales", robots: { index: false } };

export default function SellerPromotionsPage() {
  return <PromotionsView />;
}
