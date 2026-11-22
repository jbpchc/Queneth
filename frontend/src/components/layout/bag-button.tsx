"use client";

import { ShoppingBag } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";

import { spring } from "@/lib/motion";
import { useBagUi } from "@/lib/stores/bag-ui";
import { cn } from "@/lib/utils";

/** UX: Jakob's Law — bag icon top-right with a count badge that bounces on add. */
export function BagButton({ className }: { className?: string }) {
  const { count, pulse } = useBagUi();
  const reduce = useReducedMotion();
  const label = count === 1 ? "Bag, 1 item" : `Bag, ${count} items`;

  return (
    <Link
      href="/bag"
      data-bag-target
      aria-label={label}
      className={cn(
        "relative grid size-11 place-items-center rounded-full text-ink transition-colors hover:bg-surface-muted",
        className,
      )}
    >
      <ShoppingBag aria-hidden className="size-5" />
      <AnimatePresence>
        {count > 0 && (
          <motion.span
            key={pulse}
            aria-hidden
            initial={reduce ? { opacity: 0 } : { scale: 0.4, opacity: 0 }}
            animate={reduce ? { opacity: 1 } : { scale: [1.35, 1], opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={spring}
            className="tabular absolute right-0.5 top-0.5 grid h-5 min-w-5 place-items-center rounded-pill bg-accent px-1 text-[11px] font-bold text-on-accent"
          >
            {count > 99 ? "99+" : count}
          </motion.span>
        )}
      </AnimatePresence>
    </Link>
  );
}
