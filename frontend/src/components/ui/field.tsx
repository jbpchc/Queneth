"use client";

import { CircleAlert } from "lucide-react";
import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Label } from "./label";

interface FieldProps {
  label: string;
  /** UX: Cognitive Load — helper text instead of manuals. */
  hint?: ReactNode;
  error?: string;
  optional?: boolean;
  className?: string;
  children: ReactElement<Record<string, unknown>>;
}

/**
 * Label + control + helper + error, wired for assistive tech: the control gets
 * `id`, `aria-describedby` and `aria-invalid`; errors are announced via aria-live.
 */
export function Field({ label, hint, error, optional, className, children }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = `${id}-error`;
  const describedBy = [hintId, error ? errorId : undefined].filter(Boolean).join(" ") || undefined;

  const control = isValidElement(children)
    ? cloneElement(children, {
        id,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : undefined,
      })
    : children;

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label htmlFor={id}>
        {label}
        {optional && <span className="ml-1 font-normal text-ink-muted">(optional)</span>}
      </Label>
      {control}
      {hint && (
        <p id={hintId} className="text-small text-ink-muted">
          {hint}
        </p>
      )}
      <p id={errorId} aria-live="polite" className="text-small text-danger empty:hidden">
        {error ? (
          <span className="inline-flex items-center gap-1.5">
            <CircleAlert aria-hidden className="size-4" />
            {error}
          </span>
        ) : null}
      </p>
    </div>
  );
}
