import type { Metadata } from "next";

import { DashboardView } from "./dashboard-view";

export const metadata: Metadata = { title: "Dashboard", robots: { index: false } };

export default function SellerDashboardPage() {
  return <DashboardView />;
}
