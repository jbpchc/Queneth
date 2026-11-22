import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const fieldBase = [
  "w-full rounded-input border border-border-strong bg-surface px-3.5 text-body text-ink",
  "placeholder:text-ink-muted",
  "transition-[border-color,box-shadow] duration-[var(--dur-fast)] ease-brand",
  "hover:border-ink-muted",
  "focus-visible:border-accent-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-2/40",
  "aria-[invalid=true]:border-danger aria-[invalid=true]:ring-danger/30",
  "disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-60",
];

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type = "text", ...props }, ref) => (
    // UX: Fitts's Law — 48px tall fields are easy targets on touch screens.
    <input ref={ref} type={type} className={cn(fieldBase, "h-12", className)} {...props} />
  ),
);
Input.displayName = "Input";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, rows = 4, ...props }, ref) => (
  <textarea ref={ref} rows={rows} className={cn(fieldBase, "py-3", className)} {...props} />
));
Textarea.displayName = "Textarea";
