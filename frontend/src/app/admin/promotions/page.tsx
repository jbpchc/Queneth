import type { Metadata } from "next";

import { AdminPromotionsView } from "./promotions-view";

export const metadata: Metadata = { title: "Promotions", robots: { index: false } };

export default function AdminPromotionsPage() {
  return <AdminPromotionsView />;
}
