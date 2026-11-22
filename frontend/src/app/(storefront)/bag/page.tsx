import type { Metadata } from "next";

import { BagView } from "./bag-view";

export const metadata: Metadata = { title: "Your bag", robots: { index: false } };

export default function BagPage() {
  return (
    <div className="mx-auto max-w-[1280px] px-4 pb-32 pt-8 sm:px-6 md:pb-16 md:pt-12 lg:px-10">
      <BagView />
    </div>
  );
}
