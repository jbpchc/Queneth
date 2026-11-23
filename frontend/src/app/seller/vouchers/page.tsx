import type { Metadata } from "next";

import { VouchersView } from "./vouchers-view";

export const metadata: Metadata = { title: "Discount codes", robots: { index: false } };

export default function VouchersPage() {
  return <VouchersView />;
}
