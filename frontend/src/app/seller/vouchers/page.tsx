import type { Metadata } from "next";

import { VouchersView } from "./vouchers-view";

export const metadata: Metadata = { title: "Vouchers", robots: { index: false } };

export default function VouchersPage() {
  return <VouchersView />;
}
