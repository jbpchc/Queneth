import type { Metadata } from "next";

import { WalletAdminView } from "./wallet-admin-view";

export const metadata: Metadata = { title: "QueWallet", robots: { index: false } };

export default function AdminWalletPage() {
  return <WalletAdminView />;
}
