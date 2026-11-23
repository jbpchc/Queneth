import type { Metadata } from "next";

import { DropsView } from "./drops-view";

export const metadata: Metadata = { title: "Product launches", robots: { index: false } };

export default function DropsPage() {
  return <DropsView />;
}
