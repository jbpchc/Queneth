"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import type { NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

import { AccountMenu } from "./account-menu";
import { Logo } from "./logo";
import { ThemeToggle } from "./theme-toggle";

interface StudioShellProps {
  /** "Seller Studio" or "Control Room". */
  area: string;
  nav: NavItem[];
  children: ReactNode;
}

/**
 * Shell for Seller Studio and the admin Control Room: calm, strictly gridded
 * commerce surface. Sidebar on desktop, horizontally scrolling tabs on mobile.
 * UX: Common Region — the work area sits in its own bounded panel.
 */
export function StudioShell({ area, nav, children }: StudioShellProps) {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === nav[0]?.href ? pathname === href : pathname.startsWith(href);

  return (
    <div className="min-h-dvh bg-bg md:grid md:grid-cols-[248px_1fr]">
      <aside className="sticky top-0 z-30 border-b border-border bg-[var(--glass)] backdrop-blur-xl md:h-dvh md:border-b-0 md:border-r md:bg-surface md:backdrop-blur-none">
        <div className="flex h-16 items-center justify-between gap-2 px-4 md:h-20 md:px-6">
          <div className="flex flex-col leading-none">
            <Logo compact />
            <span className="mt-1 text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">
              {area}
            </span>
          </div>
          <div className="flex items-center">
            <ThemeToggle />
            <AccountMenu />
          </div>
        </div>
        <nav aria-label={area}>
          <ul className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible md:px-3 md:pb-0">
            {nav.map((item) => {
              const active = isActive(item.href);
              return (
                <li key={item.href} className="shrink-0">
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex h-11 items-center rounded-pill px-4 text-small font-semibold transition-colors md:rounded-input",
                      active
                        ? "bg-ink text-bg"
                        : "text-ink-muted hover:bg-surface-muted hover:text-ink",
                    )}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="hidden px-6 py-6 md:block">
          <Link href="/" className="text-small font-semibold text-accent-2 hover:underline">
            ← Back to shopping
          </Link>
        </div>
      </aside>
      <main id="main" tabIndex={-1} className="min-w-0 px-4 py-8 focus:outline-none sm:px-6 lg:px-10">
        {children}
      </main>
    </div>
  );
}
