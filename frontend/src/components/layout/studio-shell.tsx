"use client";

import {
  ArrowLeft,
  Box,
  Flag,
  Folder,
  House,
  Layers,
  Menu,
  Percent,
  Plug,
  Rocket,
  ScrollText,
  Settings,
  Star,
  Store,
  Ticket,
  Truck,
  Users,
  Wallet,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import type { StudioIcon, StudioNavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

import { AccountMenu } from "./account-menu";
import { Logo } from "./logo";
import { ThemeToggle } from "./theme-toggle";

const ICONS: Record<StudioIcon, LucideIcon> = {
  home: House,
  box: Box,
  layers: Layers,
  truck: Truck,
  star: Star,
  percent: Percent,
  ticket: Ticket,
  rocket: Rocket,
  wallet: Wallet,
  settings: Settings,
  store: Store,
  users: Users,
  folder: Folder,
  flag: Flag,
  plug: Plug,
  scroll: ScrollText,
};

interface StudioShellProps {
  /** "Seller Studio" or "Control Room". */
  area: string;
  nav: StudioNavItem[];
  /** Optional block at the top of the sidebar (e.g. the seller's store card). */
  sidebarTop?: ReactNode;
  children: ReactNode;
}

/**
 * Shell for Seller Studio and the admin Control Room: a calm workspace, set in
 * Inter (see `.studio` in globals.css) rather than the storefront's serif.
 * UX: Chunking — the sidebar groups pages under plain headings, each with an icon.
 * UX: Recognition over recall — a breadcrumb and one-line hint above every page
 * say where you are and what the page is for.
 * UX: Common Region — the work area sits in its own bounded panel.
 */
export function StudioShell({ area, nav, sidebarTop, children }: StudioShellProps) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const isActive = (href: string) => (href === nav[0]?.href ? pathname === href : pathname.startsWith(href));
  const current = nav.find((i) => isActive(i.href));
  const groups = [...new Set(nav.map((i) => i.group))];

  // Close the mobile drawer after navigating.
  useEffect(() => setOpen(false), [pathname]);

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center justify-between gap-2 px-5">
        <div className="flex items-center gap-2.5">
          <Logo compact />
          <Link
            href={nav[0]?.href ?? "/"}
            className="rounded-pill bg-surface-muted px-2 py-0.5 text-[11px] font-semibold text-ink-muted hover:text-ink"
          >
            {area}
          </Link>
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label="Close menu"
          className="grid size-10 place-items-center rounded-full text-ink-muted hover:bg-surface-muted md:hidden"
        >
          <X aria-hidden className="size-5" />
        </button>
      </div>
      {sidebarTop && <div className="px-3 pb-2">{sidebarTop}</div>}
      <nav aria-label={area} className="flex-1 overflow-y-auto px-3 pb-4">
        {groups.map((group) => (
          <div key={group} className="mt-4 first:mt-2">
            <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted/80">
              {group}
            </p>
            <ul className="flex flex-col gap-0.5">
              {nav
                .filter((i) => i.group === group)
                .map((item) => {
                  const active = isActive(item.href);
                  const Icon = ICONS[item.icon];
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "relative flex h-10 items-center gap-3 rounded-input px-3 text-small font-medium transition-colors",
                          active
                            ? "bg-accent/10 text-ink before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-pill before:bg-accent"
                            : "text-ink-muted hover:bg-surface-muted hover:text-ink",
                        )}
                      >
                        <Icon aria-hidden className={cn("size-[18px] shrink-0", active && "text-accent")} />
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t border-border px-3 py-3">
        <Link
          href="/"
          className="flex h-10 items-center gap-3 rounded-input px-3 text-small font-medium text-ink-muted hover:bg-surface-muted hover:text-ink"
        >
          <ArrowLeft aria-hidden className="size-[18px]" /> Back to shopping
        </Link>
      </div>
    </div>
  );

  return (
    <div className="studio min-h-dvh bg-bg md:grid md:grid-cols-[260px_1fr]">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh border-r border-border bg-surface md:block">{sidebar}</aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-[rgb(0_0_0/0.4)]"
            onClick={() => setOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 w-[280px] max-w-[85vw] border-r border-border bg-surface shadow-3">
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-col">
        {/* Top bar: where you are, what this page is for, account. */}
        <header className="sticky top-0 z-30 border-b border-border bg-[var(--glass)] backdrop-blur-xl">
          <div className="flex min-h-16 items-center gap-3 px-4 py-3 sm:px-6 lg:px-10">
            <button
              type="button"
              onClick={() => setOpen(true)}
              aria-label="Open menu"
              aria-expanded={open}
              className="grid size-10 shrink-0 place-items-center rounded-full text-ink hover:bg-surface-muted md:hidden"
            >
              <Menu aria-hidden className="size-5" />
            </button>
            <div className="flex min-w-0 flex-1 flex-col">
              <nav aria-label="Breadcrumb" className="truncate text-caption text-ink-muted">
                {area}
                {current && current.group !== "Overview" && <> / {current.group}</>}
                {current && <> / <span className="font-semibold text-ink">{current.label}</span></>}
              </nav>
              {current && <p className="hidden truncate text-small text-ink-muted sm:block">{current.hint}</p>}
            </div>
            <div className="flex shrink-0 items-center">
              <ThemeToggle />
              <AccountMenu />
            </div>
          </div>
        </header>
        <main
          id="main"
          tabIndex={-1}
          data-studio-page
          className="mx-auto w-full max-w-[1280px] min-w-0 px-4 py-8 focus:outline-none sm:px-6 lg:px-10"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
