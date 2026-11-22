/**
 * next/image loader. Each source does its own resizing at the edge:
 * - Cloudinary: insert `f_auto,q_auto,w_<width>` (AVIF/WebP per browser)
 * - Unsplash/Pexels (seed photos): their imgix-style `w`, `q`, `auto=format`
 * - anything else (local-disk uploads): served as-is, width hint appended
 */
export default function quenethImageLoader({
  src,
  width,
  quality,
}: {
  src: string;
  width: number;
  quality?: number;
}): string {
  const q = quality ?? 75;
  const cloud = src.match(/^(https:\/\/res\.cloudinary\.com\/[^/]+\/image\/upload\/)(.+)$/);
  if (cloud) {
    // Drop an existing transformation segment (it never contains "/v<digits>" or a dot).
    const rest = cloud[2]!.replace(/^(?:[a-z]{1,3}_[^/]+\/)+/, "");
    return `${cloud[1]}f_auto,q_${quality ? q : "auto"},w_${width},c_limit/${rest}`;
  }
  if (src.startsWith("https://images.unsplash.com/") || src.startsWith("https://images.pexels.com/")) {
    const url = new URL(src);
    url.searchParams.set("w", String(width));
    url.searchParams.set("q", String(q));
    url.searchParams.set("auto", "format");
    return url.toString();
  }
  return `${src}${src.includes("?") ? "&" : "?"}w=${width}`;
}
