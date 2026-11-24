"use client";

import { Bell, LogOut, ShieldCheck, Store, User, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Avatar } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout, useSession } from "@/lib/auth/session";
import { cn } from "@/lib/utils";

const iconLink =
  "grid size-11 place-items-center rounded-full text-ink transition-colors hover:bg-surface-muted";

/**
 * Avatar menu. Each account has one role (buyer, seller or admin), so it links
 * to that role's area. UI layer 4 of RBAC: links appear only for the role the
 * user holds; the proxy and the API still enforce access.
 */
export function AccountMenu({ className }: { className?: string }) {
  const { user, status, hasRole } = useSession();
  const logout = useLogout();
  const router = useRouter();
  const pathname = usePathname();
  // Server HTML never knows the session; switch to the signed-out buttons after mount.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (mounted && status === "guest") {
    // Signed out: say it in words, not just an icon (UX: recognition over recall).
    return (
      <div className={cn("grid-flow-col items-center gap-1", className)}>
        <Link
          href={`/login?next=${encodeURIComponent(pathname)}`}
          className="inline-flex h-10 items-center whitespace-nowrap rounded-pill bg-ink px-4 text-small font-semibold text-bg transition-colors hover:bg-ink/85 2xl:bg-transparent 2xl:px-3 2xl:text-ink 2xl:hover:bg-surface-muted"
        >
          Sign in
        </Link>
        {/* Room for both only on wide screens; narrower, Sign in links on to sign-up. */}
        <Link
          href="/register"
          className="hidden h-10 items-center whitespace-nowrap rounded-pill bg-ink px-4 text-small font-semibold text-bg transition-colors hover:bg-ink/85 2xl:inline-flex"
        >
          Join free
        </Link>
      </div>
    );
  }
  if (status !== "authenticated" || !user) {
    return (
      <Link href="/account" aria-label="Account" className={cn(iconLink, className)}>
        <User aria-hidden className="size-5" />
      </Link>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`Account menu for ${user.name}`}
        className={cn("grid size-11 place-items-center rounded-full hover:bg-surface-muted", className)}
      >
        <Avatar name={user.name} src={user.avatar_url} size={32} />
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>
          <p className="truncate text-small font-semibold text-ink">{user.name}</p>
          <p className="truncate text-caption text-ink-muted">{user.email}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {hasRole("SELLER") && (
          <DropdownMenuItem asChild>
            <Link href="/seller">
              <Store aria-hidden /> Seller Studio
            </Link>
          </DropdownMenuItem>
        )}
        {!hasRole("ADMIN") && (
          <DropdownMenuItem asChild>
            <Link href="/account">
              <User aria-hidden /> Your account
            </Link>
          </DropdownMenuItem>
        )}
        {!hasRole("ADMIN") && (
          <DropdownMenuItem asChild>
            <Link href="/account/wallet">
              <Wallet aria-hidden /> QueWallet
            </Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuItem asChild>
          <Link href="/account/notifications">
            <Bell aria-hidden /> Inbox
          </Link>
        </DropdownMenuItem>
        {hasRole("ADMIN") && (
          <DropdownMenuItem asChild>
            <Link href="/admin">
              <ShieldCheck aria-hidden /> Control Room
            </Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={async () => {
            await logout.mutateAsync();
            toast("Signed out", { description: "See you soon." });
            router.push("/");
            router.refresh();
          }}
        >
          <LogOut aria-hidden /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
