"use client";

import { Bell, LogOut, ShieldCheck, ShoppingBag, Store, User, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
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
 * Avatar menu. Sellers get the Shopping ↔ Seller Studio role switcher (one
 * account, roles as an array). UI layer 4 of RBAC: links appear only for roles
 * the user holds; the proxy and the API still enforce access.
 */
export function AccountMenu({ className }: { className?: string }) {
  const { user, status, hasRole } = useSession();
  const logout = useLogout();
  const router = useRouter();
  const pathname = usePathname();

  if (status !== "authenticated" || !user) {
    return (
      <Link
        href={status === "loading" ? "/account" : `/login?next=${encodeURIComponent(pathname)}`}
        aria-label="Sign in"
        className={cn(iconLink, className)}
      >
        <User aria-hidden className="size-5" />
      </Link>
    );
  }

  const inStudio = pathname.startsWith("/seller");

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
          <>
            <div role="group" aria-label="Switch mode" className="grid grid-cols-2 gap-1 rounded-pill bg-surface-muted p-1">
              {[
                { href: "/", label: "Shopping", icon: ShoppingBag, active: !inStudio },
                { href: "/seller", label: "Seller Studio", icon: Store, active: inStudio },
              ].map(({ href, label, icon: Icon, active }) => (
                <DropdownMenuItem
                  key={href}
                  asChild
                  className={cn(
                    "min-h-10 justify-center rounded-pill px-2 text-caption font-semibold",
                    active && "bg-surface shadow-1 data-[highlighted]:bg-surface",
                  )}
                >
                  <Link href={href} aria-current={active ? "page" : undefined}>
                    <Icon aria-hidden /> {label}
                  </Link>
                </DropdownMenuItem>
              ))}
            </div>
            <DropdownMenuSeparator />
          </>
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
