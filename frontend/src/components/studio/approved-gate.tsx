"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/lib/auth/session";
import { useApplication } from "@/lib/studio";

/**
 * Seller Studio opens once the boutique is approved. A seller account that is
 * still applying (or was rejected or suspended) goes to its application page.
 * UX only: the API refuses Studio calls without an approved boutique anyway.
 */
export function ApprovedSellerGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { status } = useSession();
  const app = useApplication();
  const approved = app.data?.status === "approved";

  useEffect(() => {
    if (status === "authenticated" && app.isSuccess && !approved) router.replace("/account/sell");
  }, [status, app.isSuccess, approved, router]);

  if (!approved) {
    return (
      <div className="flex flex-col gap-4 p-6" aria-busy="true" aria-label="Opening Seller Studio">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 rounded-card" />
      </div>
    );
  }
  return <>{children}</>;
}
