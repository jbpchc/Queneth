import type { Metadata } from "next";
import type { ReactNode } from "react";

import { StudioShell } from "@/components/layout/studio-shell";
import { adminNav } from "@/lib/nav";

export const metadata: Metadata = { title: { default: "Control Room", template: "%s · Control Room" } };

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <StudioShell area="Control Room" nav={adminNav}>
      {children}
    </StudioShell>
  );
}
