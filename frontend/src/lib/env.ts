/**
 * Runtime configuration. Values come from frontend/.env — nothing is hardcoded.
 * The browser uses NEXT_PUBLIC_API_URL; server components prefer API_INTERNAL_URL
 * (the Docker service hostname) when it is set.
 */
const publicApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "";

export const env = {
  apiUrl: publicApiUrl,
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL ?? "",
} as const;

export function serverApiUrl(): string {
  return process.env.API_INTERNAL_URL || publicApiUrl;
}
