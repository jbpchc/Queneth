"use client";

import { useBag } from "@/lib/shop";

/** Keeps the header bag badge in sync with the server bag. Renders nothing. */
export function BagSync() {
  useBag();
  return null;
}
