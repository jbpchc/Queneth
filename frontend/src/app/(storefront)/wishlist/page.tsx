import type { Metadata } from "next";

import { WishlistView } from "./wishlist-view";

export const metadata: Metadata = { title: "Wishlist", robots: { index: false } };

export default function WishlistPage() {
  return (
    <div className="mx-auto max-w-[1536px] px-4 pb-16 pt-8 sm:px-6 md:pt-12 lg:px-10">
      <WishlistView />
    </div>
  );
}
