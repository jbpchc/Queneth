import type { Metadata } from "next";
import Link from "next/link";

import { Logo } from "@/components/layout/logo";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Not available", robots: { index: false } };

/** Branded 403, shown by the proxy when a signed-in user lacks the role. */
export default function ForbiddenPage() {
  return (
    <main id="main" className="grain grid min-h-dvh place-items-center px-4">
      <div className="relative z-[2] flex max-w-lg flex-col items-center gap-6 text-center">
        <Logo />
        <p className="font-display text-[clamp(6rem,20vw,11rem)] leading-none text-ink/10">403</p>
        <h1 className="-mt-10 text-h1 text-ink">This room is by appointment.</h1>
        <p className="text-ink-muted">
          Your account doesn&apos;t have access to this area. If you run a boutique, apply to sell
          on Queneth and we&apos;ll open Seller Studio for you.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Button asChild variant="primary" size="lg">
            <Link href="/">Back to shopping</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/account">Your account</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
