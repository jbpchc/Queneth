/**
 * Only allow same-site relative paths in `?next=` so the login page can't be
 * used as an open redirect (e.g. `?next=https://evil.example` or `//evil`).
 */
export function safeNext(next: string | null | undefined, fallback = "/"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) {
    return fallback;
  }
  if (next.startsWith("/login") || next.startsWith("/register")) return fallback;
  return next;
}

/** Route rules shared by the Next.js proxy and client guards (UX only). */
export const PROTECTED_PREFIXES = ["/account", "/checkout", "/seller", "/admin"] as const;
export const ROLE_PREFIXES: Record<string, "SELLER" | "ADMIN"> = {
  "/seller": "SELLER",
  "/admin": "ADMIN",
};
