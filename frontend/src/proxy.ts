import { NextResponse, type NextRequest } from "next/server";

import { PROTECTED_PREFIXES, ROLE_PREFIXES } from "@/lib/auth/redirect";

/**
 * Route guards — enforcement layer 3 (spec §7). CONVENIENCE ONLY, NOT SECURITY:
 * the `qn_session` cookie is a readable hint listing role names. Anyone can
 * forge it; doing so only reveals an empty shell, because every API call is
 * authorised by the Python backend.
 */
const SESSION_HINT_COOKIE = "qn_session";

function matches(pathname: string, prefix: string) {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hint = request.cookies.get(SESSION_HINT_COOKIE)?.value;
  const roles = hint ? hint.split(".") : [];

  // Signed-in users don't need the sign-in pages.
  if (hint && (pathname === "/login" || pathname === "/register")) {
    const home = roles.includes("ADMIN") ? "/admin" : roles.includes("SELLER") ? "/seller" : "/account";
    return NextResponse.redirect(new URL(home, request.url));
  }

  if (!PROTECTED_PREFIXES.some((p) => matches(pathname, p))) return NextResponse.next();

  if (!hint) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }

  for (const [prefix, role] of Object.entries(ROLE_PREFIXES)) {
    if (matches(pathname, prefix) && !roles.includes(role)) {
      // Branded 403 at the same URL, with the right status code.
      return NextResponse.rewrite(new URL("/403", request.url), { status: 403 });
    }
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/account/:path*", "/checkout/:path*", "/seller/:path*", "/admin/:path*", "/login", "/register"],
};
