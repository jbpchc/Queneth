import type { ReactNode } from "react";

import { Logo } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";

/**
 * Editorial split layout for sign-in and sign-up: a quiet typographic panel on
 * desktop, just the form on mobile. One task per screen (Cognitive Load).
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      <aside
        aria-hidden
        className="grain relative hidden overflow-hidden border-r border-border bg-surface-muted lg:flex lg:flex-col lg:justify-between lg:p-14"
      >
        <div className="relative z-[2]">
          <Logo />
        </div>
        <div className="relative z-[2] flex max-w-lg flex-col gap-6">
          <p className="font-display text-h1 italic leading-[1.1] text-ink">
            “Style is knowing the drape before you touch the fabric.”
          </p>
          <p className="text-small uppercase tracking-[0.14em] text-ink-muted">
            Independent boutiques · Authenticated pieces · Notes, not noise
          </p>
        </div>
        <div className="pointer-events-none absolute -bottom-24 -right-24 size-[420px] rounded-full bg-lilac/50 blur-3xl" />
        <div className="pointer-events-none absolute -right-10 top-24 size-[220px] rounded-full bg-accent/15 blur-3xl" />
      </aside>
      <div className="flex flex-col">
        <header className="flex h-16 items-center justify-between px-4 sm:px-8 lg:justify-end">
          <span className="lg:hidden">
            <Logo compact />
          </span>
          <ThemeToggle />
        </header>
        <main id="main" tabIndex={-1} className="flex flex-1 items-center justify-center px-4 pb-16 pt-6 focus:outline-none sm:px-8">
          <div className="w-full max-w-[420px]">{children}</div>
        </main>
      </div>
    </div>
  );
}
