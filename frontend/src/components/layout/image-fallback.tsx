"use client";

import { useEffect } from "react";

import { env } from "@/lib/env";

const CDN = "https://images.unsplash.com/";
const DEFAULT_FALLBACK = "/fallback-art.svg";

/** The SVG art a photo URL carries in `fb=` (relative to the API), or a neutral default. */
function fallbackFor(src: string): string {
  try {
    const fb = new URL(src).searchParams.get("fb");
    if (fb) return fb.startsWith("/") ? `${env.apiUrl}${fb}` : fb;
  } catch {
    // not a URL we understand: use the default
  }
  return DEFAULT_FALLBACK;
}

function swap(img: HTMLImageElement) {
  const src = img.currentSrc || img.src;
  if (!src.startsWith(CDN) || img.dataset.fellBack) return;
  img.dataset.fellBack = "1";
  img.removeAttribute("srcset");
  img.src = fallbackFor(src);
}

/**
 * Seed photos load from Unsplash's CDN. When it can't be reached (an offline
 * demo, a blocked network), every such image quietly switches to the
 * generated SVG art it was paired with — one listener for the whole app
 * instead of an onError on each <Image>. UX: the layout never shows broken
 * image icons.
 */
export function ImageFallback() {
  useEffect(() => {
    const onError = (e: Event) => {
      if (e.target instanceof HTMLImageElement) swap(e.target);
    };
    document.addEventListener("error", onError, true);
    // Images that already failed before this listener existed (before hydration).
    for (const img of Array.from(document.images)) {
      if (img.complete && img.naturalWidth === 0) swap(img);
    }
    return () => document.removeEventListener("error", onError, true);
  }, []);
  return null;
}
