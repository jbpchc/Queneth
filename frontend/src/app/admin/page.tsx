import type { Metadata } from "next";

import { OverviewView } from "./overview-view";

export const metadata: Metadata = { title: "Overview", robots: { index: false } };

export default function AdminOverviewPage() {
  return <OverviewView />;
}
