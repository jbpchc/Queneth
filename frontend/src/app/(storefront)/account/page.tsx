import type { Metadata } from "next";

import { AccountOverview } from "./account-overview";

export const metadata: Metadata = { title: "Your account", robots: { index: false } };

export default function AccountPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 md:py-14 lg:px-10">
      <AccountOverview />
    </div>
  );
}
