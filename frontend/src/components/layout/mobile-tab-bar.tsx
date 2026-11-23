"use client";

import { Heart, House, Search, ShoppingBag, User } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useSession } from "@/lib/auth/session";
import { useBagUi } from "@/lib/stores/bag-ui";
import { cn } from "@/lib/utils";

/**
 * Mobile bottom tab bar.
 * UX: Serial Position effect — Home first, Profile last.
 * UX: Fitts's Law — each tab is a full-height thumb target in the easy reach zone.
 */
const tabs = [
  { href: "/", label: "Home", icon: House, match: (p: string) => p === "/" },
  { href: "/search", label: "Search", icon: Search, match: (p: string) => p.startsWith("/search") },
  { href: "/wishlist", label: "Wishlist", icon: Heart, match: (p: string) => p.startsWith("/wishlist") },
  { href: "/bag", label: "Bag", icon: ShoppingBag, match: (p: string) => p.startsWith("/bag") },
  { href: "/account", label: "Profile", icon: User, match: (p: string) => p.startsWith("/account") },
] as const;

export function MobileTabBar() {
  const pathname = usePathname();
  const count = useBagUi((s) => s.count);
  const { status } = useSession();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <nav
      aria-label="Quick navigation"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-[var(--glass)] pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden"
    >
      <ul className="grid grid-cols-5">
        {tabs.map(({ href: tabHref, label: tabLabel, icon: Icon, match }) => {
          const active = match(pathname);
          // Signed out, the last tab says "Sign in" and goes straight to the form.
          const guestTab = tabHref === "/account" && mounted && status === "guest";
          const href = guestTab ? "/login" : tabHref;
          const label = guestTab ? "Sign in" : tabLabel;
          return (
            <li key={tabHref}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex h-16 flex-col items-center justify-center gap-1 text-[11px] font-semibold transition-colors",
                  active ? "text-ink" : "text-ink-muted",
                )}
              >
                <span className="relative">
                  <Icon
                    aria-hidden
                    className={cn("size-[22px]", active && "fill-current/10")}
                    strokeWidth={active ? 2.25 : 1.75}
                  />
                  {href === "/bag" && count > 0 && (
                    <span className="tabular absolute -right-2.5 -top-1.5 grid h-4 min-w-4 place-items-center rounded-pill bg-accent px-1 text-[10px] font-bold text-on-accent">
                      {count > 99 ? "99+" : count}
                      <span className="sr-only"> items</span>
                    </span>
                  )}
                </span>
                {label}
                {active && (
                  <span aria-hidden className="absolute top-0 h-0.5 w-8 rounded-pill bg-ink" />
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
