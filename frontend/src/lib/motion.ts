import type { Transition } from "motion/react";

/** Motion tokens mirrored from tokens.css for Framer Motion (the `motion` package). */
export const duration = {
  instant: 0.1,
  fast: 0.18,
  base: 0.28,
  celebrate: 0.9,
} as const;

export const easeOut = [0.22, 1, 0.36, 1] as const;

/** --ease-spring: buttons, hearts, cart badge. */
export const spring: Transition = { type: "spring", stiffness: 400, damping: 28 };

export const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: duration.base, ease: easeOut } },
} as const;

/** Reduced-motion counterpart: same timing, opacity only. */
export const fadeOnly = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: duration.base, ease: easeOut } },
} as const;

/**
 * Multi-keyframe "pop" (e.g. scale 1 → 1.3 → 1). Springs only animate between
 * two keyframes, so pops use a short tween with a back-out overshoot instead.
 */
export const pop: Transition = { type: "tween", duration: 0.34, ease: [0.34, 1.56, 0.64, 1] };
