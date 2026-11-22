"use client";

import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { Check } from "lucide-react";
import { forwardRef, type ComponentPropsWithoutRef, type ComponentRef } from "react";

import { cn } from "@/lib/utils";

export const Checkbox = forwardRef<
  ComponentRef<typeof CheckboxPrimitive.Root>,
  ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      // 22px box inside a 44px hit area (UX: Fitts's Law) via the ::before overlay.
      "relative size-[22px] shrink-0 rounded-[6px] border border-border-strong bg-surface",
      "before:absolute before:-inset-[11px] before:content-['']",
      "transition-colors duration-[var(--dur-fast)] ease-brand",
      "data-[state=checked]:border-ink data-[state=checked]:bg-ink data-[state=checked]:text-bg",
      "disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator className="flex items-center justify-center">
      <Check aria-hidden className="size-4" strokeWidth={3} />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = "Checkbox";

export const Switch = forwardRef<
  ComponentRef<typeof SwitchPrimitive.Root>,
  ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    ref={ref}
    className={cn(
      "relative inline-flex h-7 w-12 shrink-0 items-center rounded-pill border border-border-strong bg-surface-muted",
      "before:absolute before:-inset-2 before:content-['']",
      "transition-colors duration-[var(--dur-fast)] ease-brand",
      "data-[state=checked]:border-accent-2 data-[state=checked]:bg-accent-2",
      "disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...props}
  >
    <SwitchPrimitive.Thumb
      className={cn(
        "block size-5 translate-x-1 rounded-full bg-surface shadow-1",
        "transition-transform duration-[var(--dur-fast)] ease-brand",
        "data-[state=checked]:translate-x-[22px]",
      )}
    />
  </SwitchPrimitive.Root>
));
Switch.displayName = "Switch";
