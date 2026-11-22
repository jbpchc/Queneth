import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const site = process.env.NEXT_PUBLIC_SITE_URL ?? "";
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Private, per-user or utility pages stay out of search results.
        disallow: ["/account", "/bag", "/wishlist", "/checkout", "/seller", "/admin", "/search", "/styleguide"],
      },
    ],
    sitemap: `${site}/sitemap.xml`,
  };
}
