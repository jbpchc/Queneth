"use client";

import { Heart } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";

import { pop, spring } from "@/lib/motion";
import { useToggleWishlist, useWishlistIds } from "@/lib/shop";
import { cn } from "@/lib/utils";

const PARTICLES = Array.from({ length: 8 }, (_, i) => (i / 8) * Math.PI * 2);

/**
 * Dopamine moment (spec §6): spring scale 1 → 1.3 → 1 plus a small Que Magenta
 * particle burst. Reduced motion: a simple color change, no movement.
 */
export function WishlistHeart({
  productId,
  title,
  className,
  size = "md",
}: {
  productId: string;
  title: string;
  className?: string;
  size?: "md" | "lg";
}) {
  const { data: ids } = useWishlistIds();
  const toggle = useToggleWishlist();
  const reduce = useReducedMotion();
  const [burst, setBurst] = useState(0);
  const saved = ids?.has(productId) ?? false;

  return (
    <motion.button
      type="button"
      aria-pressed={saved}
      aria-label={saved ? `Remove ${title} from wishlist` : `Save ${title} to wishlist`}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (toggle(productId, !saved) && !saved) setBurst((b) => b + 1);
      }}
      whileTap={reduce ? undefined : { scale: 0.88 }}
      className={cn(
        "relative grid place-items-center rounded-full bg-surface/85 text-ink shadow-1 backdrop-blur transition-colors hover:bg-surface",
        size === "lg" ? "size-12" : "size-11",
        className,
      )}
    >
      <motion.span
        key={`heart-${burst}`}
        initial={false}
        animate={!reduce && burst > 0 ? { scale: [1, 1.3, 1] } : { scale: 1 }}
        transition={pop}
        className="grid place-items-center"
      >
        <Heart
          aria-hidden
          className={cn("size-5 transition-colors duration-[var(--dur-fast)]", saved && "fill-accent text-accent")}
        />
      </motion.span>
      <AnimatePresence>
        {!reduce && burst > 0 && (
          <span key={burst} aria-hidden className="pointer-events-none absolute inset-0">
            {PARTICLES.map((angle) => (
              <motion.span
                key={angle}
                className="absolute left-1/2 top-1/2 size-1.5 rounded-full bg-accent"
                initial={{ x: "-50%", y: "-50%", opacity: 1, scale: 1 }}
                animate={{
                  x: `calc(-50% + ${Math.cos(angle) * 22}px)`,
                  y: `calc(-50% + ${Math.sin(angle) * 22}px)`,
                  opacity: 0,
                  scale: 0.4,
                }}
                transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              />
            ))}
          </span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}
