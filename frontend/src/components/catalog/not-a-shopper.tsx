import { ShieldCheck, Store } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";

/** Shown on shopping pages to seller and admin accounts, which never shop. */
export function NotAShopper({ admin }: { admin: boolean }) {
  return (
    <EmptyState
      icon={admin ? ShieldCheck : Store}
      title="Shopping is for buyer accounts"
      description={
        admin
          ? "Admin accounts run the marketplace. Sign in with a buyer account to shop."
          : "Seller accounts run a boutique. To shop, sign in with a separate buyer account."
      }
      action={
        <Button asChild variant="primary">
          <Link href={admin ? "/admin" : "/seller"}>{admin ? "Open Control Room" : "Open Seller Studio"}</Link>
        </Button>
      }
    />
  );
}
