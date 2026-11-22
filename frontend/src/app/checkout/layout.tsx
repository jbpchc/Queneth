import { Lock } from "lucide-react";
import type { ReactNode } from "react";

import { Logo } from "@/components/layout/logo";

/**
 * Focused checkout shell: logo and a way back to the bag, no store navigation.
 * UX: Hick's Law — fewer exits while paying; UX: Jakob's Law — the familiar
 * "secure checkout" header shoppers know from other stores.
 */
export default function CheckoutLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b border-border bg-bg">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
          <Logo className="shrink-0" />
          <span className="ml-auto inline-flex items-center gap-1.5 text-small font-semibold text-ink-muted">
            <Lock aria-hidden className="size-4" /> Secure checkout
          </span>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 pb-8 pt-8 focus:outline-none sm:px-6 md:pt-12">
        {children}
      </main>
    </div>
  );
}
