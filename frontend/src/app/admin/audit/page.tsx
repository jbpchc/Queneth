import type { Metadata } from "next";

import { AuditView } from "./audit-view";

export const metadata: Metadata = { title: "Audit log", robots: { index: false } };

export default function AdminAuditPage() {
  return <AuditView />;
}
