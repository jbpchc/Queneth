import type { Metadata } from "next";

import { ModerationView } from "./moderation-view";

export const metadata: Metadata = { title: "Moderation", robots: { index: false } };

export default function AdminModerationPage() {
  return <ModerationView />;
}
