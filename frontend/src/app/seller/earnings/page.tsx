import type { Metadata } from "next";

import { EarningsView } from "./earnings-view";

export const metadata: Metadata = { title: "Earnings", robots: { index: false } };

export default function EarningsPage() {
  return <EarningsView />;
}
