import type { Metadata } from "next";

import { SettingsView } from "./settings-view";

export const metadata: Metadata = { title: "Store settings", robots: { index: false } };

export default function SettingsPage() {
  return <SettingsView />;
}
