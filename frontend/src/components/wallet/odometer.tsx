"use client";

import { useReducedMotion } from "motion/react";

import { cn } from "@/lib/utils";

const DIGITS = "0123456789";

/**
 * Dopamine moment (spec §6): the balance rolls digit by digit like an odometer
 * after top-ups and payments. Each digit is a vertical 0–9 strip translated
 * into place. Reduced motion: digits change instantly.
 */
export function Odometer({ value, className }: { value: number; className?: string }) {
  const reduce = useReducedMotion();
  const text = new Intl.NumberFormat("en-PH").format(Math.trunc(value));
  return (
    <span className={cn("tabular relative inline-flex overflow-clip leading-none", className)} aria-live="polite">
      <span className="sr-only">{text}</span>
      {text.split("").map((ch, i) => {
        const key = `${text.length - i}`; // keyed from the right so digits keep their place
        if (!DIGITS.includes(ch)) {
          return (
            <span key={key} aria-hidden>
              {ch}
            </span>
          );
        }
        return (
          <span key={key} aria-hidden className="relative inline-block h-[1em] w-[0.62em] overflow-clip">
            <span
              className="absolute inset-x-0 top-0 flex flex-col"
              style={{
                transform: `translateY(-${Number(ch)}em)`,
                transition: reduce ? "none" : `transform 900ms cubic-bezier(0.22, 1, 0.36, 1) ${i * 40}ms`,
              }}
            >
              {DIGITS.split("").map((d) => (
                <span key={d} className="h-[1em] text-center">
                  {d}
                </span>
              ))}
            </span>
          </span>
        );
      })}
    </span>
  );
}
