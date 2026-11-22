"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

/**
 * 6-digit QueWallet PIN: six boxes, auto-advance, backspace goes back, paste
 * fills all six (Postel's Law: "123 456" works). Digits are masked.
 * UX: Mental Model — the familiar e-wallet PIN pad, a deliberate pause before money moves.
 */
export function PinInput({
  value,
  onChange,
  label,
  autoFocus,
  invalid,
  disabled,
  onComplete,
}: {
  value: string;
  onChange: (v: string) => void;
  label: string;
  autoFocus?: boolean;
  invalid?: boolean;
  disabled?: boolean;
  onComplete?: (v: string) => void;
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  useEffect(() => {
    if (autoFocus) refs.current[0]?.focus();
  }, [autoFocus]);

  // Keystrokes can arrive faster than React re-renders (fast typing, autofill):
  // always build on the latest digits, not the value from the last render.
  const latest = useRef(value);
  latest.current = value;

  const set = (next: string) => {
    const clean = next.replace(/\D/g, "").slice(0, 6);
    latest.current = clean;
    onChange(clean);
    if (clean.length === 6) onComplete?.(clean);
    return clean;
  };

  return (
    <fieldset className="flex flex-col gap-2" disabled={disabled}>
      <legend className="mb-2 text-small font-semibold text-ink">{label}</legend>
      <div className="flex gap-2" role="group" aria-label={label}>
        {Array.from({ length: 6 }, (_, i) => (
          <input
            key={i}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="password"
            inputMode="numeric"
            autoComplete="one-time-code"
            aria-label={`${label}, digit ${i + 1} of 6`}
            aria-invalid={invalid || undefined}
            value={value[i] ?? ""}
            onChange={(e) => {
              const current = latest.current;
              const digits = e.target.value.replace(/\D/g, "");
              if (!digits) return;
              // Several digits at once (autofill, IME, dictation): fill onward like a paste.
              // (Typing over a filled box yields old + new digit: that's a single keystroke.)
              const typedOver = !!current[i] && digits.length === 2;
              if (digits.length > 1 && !typedOver) {
                const filled = set(current.slice(0, i) + digits);
                refs.current[Math.min(filled.length, 5)]?.focus();
                return;
              }
              const digit = digits.slice(-1);
              const chars = current.padEnd(6, " ").split("");
              chars[i] = digit;
              set(chars.join("").replace(/ /g, ""));
              refs.current[Math.min(i + 1, 5)]?.focus();
            }}
            onKeyDown={(e) => {
              const current = latest.current;
              if (e.key === "Backspace") {
                e.preventDefault();
                const target = current[i] ? i : Math.max(i - 1, 0);
                set(current.slice(0, target) + current.slice(target + 1));
                refs.current[target]?.focus();
              } else if (e.key === "ArrowLeft") refs.current[Math.max(i - 1, 0)]?.focus();
              else if (e.key === "ArrowRight") refs.current[Math.min(i + 1, 5)]?.focus();
            }}
            onPaste={(e) => {
              e.preventDefault();
              const pasted = set(e.clipboardData.getData("text"));
              refs.current[Math.min(pasted.length, 5)]?.focus();
            }}
            className={cn(
              "h-14 w-12 rounded-input border bg-surface text-center font-display text-h3 text-ink",
              "focus-visible:border-accent-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-2/40",
              invalid ? "border-danger" : "border-border-strong",
            )}
          />
        ))}
      </div>
    </fieldset>
  );
}
