import type { Metadata } from "next";

import { WalletView } from "./wallet-view";

export const metadata: Metadata = { title: "QueWallet", robots: { index: false } };

export default function WalletPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 pb-16 pt-8 sm:px-6 md:pt-12">
      <WalletView />
    </div>
  );
}
