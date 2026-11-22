"use client";

import { Heart, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useRef } from "react";

import { SearchBox } from "@/components/catalog/search-box";

import { useHotkey } from "@/hooks/use-hotkey";
import { useScrolled } from "@/hooks/use-scrolled";
import { primaryNav } from "@/lib/nav";
import { cn } from "@/lib/utils";

import { AccountMenu } from "./account-menu";
import { BagButton } from "./bag-button";
import { Logo } from "./logo";
import { ThemeToggle } from "./theme-toggle";

const iconLink =
  "grid size-11 place-items-center rounded-full text-ink transition-colors hover:bg-surface-muted";

/**
 * Frosted-glass sticky header that shrinks on scroll.
 * UX: Jakob's Law — logo top-left, search in the header, bag top-right.
 */
export function SiteHeader() {
  const scrolled = useScrolled();
  const pathname = usePathname();
  const searchRef = useRef<HTMLInputElement>(null);

  // UX: Flow — "/" focuses search from anywhere.
  const focusSearch = useCallback((e: KeyboardEvent) => {
    if (!searchRef.current) return;
    e.preventDefault();
    searchRef.current.focus();
  }, []);
  useHotkey("/", focusSearch);

  return (
    <header
      className={cn(
        "sticky top-0 z-40 border-b backdrop-blur-xl backdrop-saturate-150 transition-[border-color,box-shadow] duration-[var(--dur-base)] ease-brand",
        "bg-[var(--glass)]",
        scrolled ? "border-border shadow-1" : "border-transparent",
      )}
    >
      <div
        className={cn(
          "mx-auto flex max-w-[1536px] items-center gap-4 px-4 transition-[height] duration-[var(--dur-base)] ease-brand sm:px-6 lg:px-10",
          scrolled ? "h-14" : "h-16 md:h-20",
        )}
      >
        <Logo compact={scrolled} />

        <nav aria-label="Primary" className="hidden flex-1 justify-center md:flex">
          <ul className="flex items-center gap-0.5 lg:gap-1">
            {primaryNav.map((item) => {
              const active = item.href !== "/" && pathname.startsWith(item.href.split("?")[0]!);
              return (
                <li key={item.label} className="group/nav relative">
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative inline-flex h-11 items-center rounded-pill px-3 text-small font-semibold text-ink-muted transition-colors hover:text-ink lg:px-3.5",
                      active && "text-ink",
                      item.label === "New" && "text-ink",
                    )}
                  >
                    {item.label}
                  </Link>
                  {item.children && (
                    // UX: Hick's Law — ≤ 8 subcategories per category in the mega-menu.
                    <div className="invisible absolute left-1/2 top-full z-50 w-60 -translate-x-1/2 pt-2 opacity-0 transition-[opacity,visibility] duration-[var(--dur-fast)] ease-brand group-focus-within/nav:visible group-focus-within/nav:opacity-100 group-hover/nav:visible group-hover/nav:opacity-100">
                      <ul className="rounded-card border border-border bg-surface p-2 shadow-3">
                        {item.children.map((child) => (
                          <li key={child.href}>
                            <Link
                              href={child.href}
                              className="flex h-11 items-center rounded-input px-3 text-small text-ink transition-colors hover:bg-surface-muted"
                            >
                              {child.label}
                            </Link>
                          </li>
                        ))}
                        <li className="mt-1 border-t border-border pt-1">
                          <Link
                            href={item.href}
                            className="flex h-11 items-center rounded-input px-3 text-small font-semibold text-accent-2 hover:bg-surface-muted"
                          >
                            All {item.label.toLowerCase()}
                          </Link>
                        </li>
                      </ul>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="ml-auto flex items-center gap-1 md:ml-0">
          <SearchBox ref={searchRef} className="hidden w-64 lg:block xl:w-72" />
          <Link href="/search" aria-label="Search" className={cn(iconLink, "lg:hidden")}>
            <Search aria-hidden className="size-5" />
          </Link>
          <ThemeToggle className="hidden sm:grid" />
          <Link href="/wishlist" aria-label="Wishlist" className={cn(iconLink, "hidden md:grid")}>
            <Heart aria-hidden className="size-5" />
          </Link>
          <AccountMenu className="hidden md:grid" />
          <BagButton />
        </div>
      </div>
    </header>
  );
}
