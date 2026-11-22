import type { Metadata } from "next";
import type { ReactNode } from "react";

import { StudioShell } from "@/components/layout/studio-shell";
import { sellerNav } from "@/lib/nav";

export const metadata: Metadata = { title: { default: "Seller Studio", template: "%s · Seller Studio" } };

export default function SellerLayout({ children }: { children: ReactNode }) {
  return (
    <StudioShell area="Seller Studio" nav={sellerNav}>
      {children}
    </StudioShell>
  );
}
