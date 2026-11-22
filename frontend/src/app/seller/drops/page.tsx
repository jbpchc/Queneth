import type { Metadata } from "next";

import { DropsView } from "./drops-view";

export const metadata: Metadata = { title: "Drops", robots: { index: false } };

export default function DropsPage() {
  return <DropsView />;
}
