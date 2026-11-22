import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * tailwind-merge must know Queneth's custom theme scales; otherwise it can't
 * tell `text-small` (font size) from `text-bg` (color) and drops one of them.
 */
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: ["display", "h1", "h2", "h3", "body", "small", "caption"],
      radius: ["input", "card", "pill"],
      shadow: ["1", "2", "3"],
      ease: ["brand"],
    },
  },
});

/** Merge class names, letting later Tailwind utilities win over earlier ones. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
