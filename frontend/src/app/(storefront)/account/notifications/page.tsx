import type { Metadata } from "next";

import { Inbox } from "./inbox";

export const metadata: Metadata = { title: "Inbox", robots: { index: false } };

export default function NotificationsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 md:py-14">
      <Inbox />
    </div>
  );
}
