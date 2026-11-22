import type { Metadata } from "next";

import { SellView } from "./sell-view";

export const metadata: Metadata = { title: "Become a seller", robots: { index: false } };

export default function SellPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 pb-16 pt-8 sm:px-6 md:pt-12">
      <SellView />
    </div>
  );
}
