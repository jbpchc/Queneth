import type { MetadataRoute } from "next";

import { createServerApi } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const site = () => process.env.NEXT_PUBLIC_SITE_URL ?? "";

/** sitemap.xml: static pages, categories, boutiques, collections and every visible product. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const api = createServerApi();
  const base = site();
  const entries: MetadataRoute.Sitemap = [
    { url: `${base}/`, changeFrequency: "daily", priority: 1 },
    { url: `${base}/drops`, changeFrequency: "daily", priority: 0.8 },
    { url: `${base}/boutiques`, changeFrequency: "weekly", priority: 0.6 },
  ];
  try {
    const [cats, boutiques, collections] = await Promise.all([
      api.GET("/api/v1/catalog/categories"),
      api.GET("/api/v1/catalog/boutiques"),
      api.GET("/api/v1/catalog/collections"),
    ]);
    for (const c of cats.data ?? []) {
      entries.push({ url: `${base}/c/${c.slug}`, changeFrequency: "daily", priority: 0.8 });
      for (const s of c.subcategories) entries.push({ url: `${base}/c/${c.slug}/${s.slug}`, changeFrequency: "daily", priority: 0.6 });
    }
    for (const b of boutiques.data ?? []) entries.push({ url: `${base}/b/${b.slug}`, changeFrequency: "weekly", priority: 0.6 });
    for (const c of collections.data ?? []) entries.push({ url: `${base}/collections/${c.slug}`, changeFrequency: "weekly", priority: 0.7 });

    let cursor: string | null | undefined;
    do {
      const page = await api.GET("/api/v1/catalog/products", {
        params: { query: { limit: 96, sort: "newest", ...(cursor ? { cursor } : {}) } },
      });
      for (const p of page.data?.items ?? []) entries.push({ url: `${base}/p/${p.slug}`, changeFrequency: "weekly", priority: 0.7 });
      cursor = page.data?.next_cursor;
    } while (cursor);
  } catch {
    // API unreachable: still serve the static entries.
  }
  return entries;
}
