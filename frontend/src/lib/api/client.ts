import createClient from "openapi-fetch";

import { env, serverApiUrl } from "@/lib/env";

import type { components, paths } from "./schema";

export type ApiSchemas = components["schemas"];
export type ApiError = ApiSchemas["ErrorResponse"]["error"];

/** Cookie names set by the API (see backend/app/core/security.py). */
export const CSRF_COOKIE = "qn_csrf";
export const SESSION_HINT_COOKIE = "qn_session";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

const apiOrigin = env.apiUrl.replace(/\/api\/v1\/?$/, "");

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

/** Double-submit CSRF: echo the readable cookie in a header on mutations. */
function withCsrf(request: Request): Request {
  const token = readCookie(CSRF_COOKIE);
  if (token && !SAFE_METHODS.has(request.method)) request.headers.set("X-CSRF-Token", token);
  return request;
}

let refreshing: Promise<boolean> | null = null;

/** One shared refresh at a time, however many requests hit a 401 together. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${apiOrigin}/api/v1/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: readCookie(CSRF_COOKIE) ? { "X-CSRF-Token": readCookie(CSRF_COOKIE)! } : {},
  })
    .then((res) => res.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/**
 * Access tokens live 15 minutes. When one expires mid-session, refresh once
 * (rotating the refresh token) and replay the request, so the user never sees it.
 */
async function authFetch(request: Request): Promise<Response> {
  const replay = request.clone();
  const response = await fetch(withCsrf(request));
  const isAuthCall = new URL(request.url).pathname.startsWith("/api/v1/auth/");
  if (response.status !== 401 || isAuthCall || !readCookie(SESSION_HINT_COOKIE)) return response;
  return (await refreshSession()) ? fetch(withCsrf(replay)) : response;
}

/**
 * Typed REST client generated from FastAPI's OpenAPI schema (`npm run gen:api`).
 * `credentials: "include"` sends the httpOnly auth cookies; the frontend never
 * stores tokens itself.
 */
export const api = createClient<paths>({
  baseUrl: apiOrigin,
  credentials: "include",
  fetch: authFetch,
});

/** Server-component client: reaches the API over the internal network when available. */
export function createServerApi() {
  return createClient<paths>({
    baseUrl: serverApiUrl().replace(/\/api\/v1\/?$/, ""),
    cache: "no-store",
  });
}

/** Normalise any thrown/returned error into the API's error shape for UI states. */
export function toApiError(error: unknown): ApiError {
  if (error && typeof error === "object" && "error" in error) {
    const inner = (error as { error: unknown }).error;
    if (inner && typeof inner === "object" && "code" in inner && "message" in inner) {
      return inner as ApiError;
    }
  }
  return {
    code: "network_error",
    message: "We couldn't reach Queneth. Check your connection and try again.",
    details: null,
  };
}

/** Map a 422/409 envelope onto form fields: { email: "Already registered." }. */
export function fieldErrors(error: ApiError): Record<string, string> {
  const out: Record<string, string> = {};
  if (Array.isArray(error.details)) {
    for (const d of error.details as { field?: string; message?: string }[]) {
      if (d.field && d.message && !out[d.field]) out[d.field] = d.message.replace(/^Value error, /, "");
    }
  }
  return out;
}
