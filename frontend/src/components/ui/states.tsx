import { CircleAlert, CircleCheck, Info, TriangleAlert, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  /** UX: Paradox of the Active User — empty states always offer the next action. */
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-4 rounded-card border border-dashed border-border-strong/60 bg-surface px-6 py-14 text-center",
        className,
      )}
    >
      {Icon && (
        <span className="grid size-14 place-items-center rounded-full bg-surface-muted text-ink">
          <Icon aria-hidden className="size-6" />
        </span>
      )}
      <div className="flex max-w-md flex-col gap-2">
        <h2 className="text-h3 text-ink">{title}</h2>
        {description && <p className="text-ink-muted">{description}</p>}
      </div>
      {action && <div className="mt-2 flex flex-wrap justify-center gap-3">{action}</div>}
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}

export function ErrorState({
  title = "Something didn't load",
  message,
  onRetry,
  retryLabel = "Try again",
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center gap-3 rounded-card border border-danger/30 bg-danger-soft px-6 py-10 text-center",
        className,
      )}
    >
      <TriangleAlert aria-hidden className="size-7 text-danger" />
      <h2 className="text-h3 text-ink">{title}</h2>
      <p className="max-w-md text-ink-muted">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 inline-flex h-11 items-center rounded-pill border border-border-strong bg-surface px-5 text-small font-semibold text-ink hover:bg-surface-muted"
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}

const alertTone = {
  info: { icon: Info, className: "border-accent-2/30 bg-accent-2/8 text-ink", iconClass: "text-accent-2" },
  success: { icon: CircleCheck, className: "border-success/30 bg-success-soft text-ink", iconClass: "text-success" },
  warning: { icon: TriangleAlert, className: "border-warning/30 bg-warning-soft text-ink", iconClass: "text-warning" },
  danger: { icon: CircleAlert, className: "border-danger/30 bg-danger-soft text-ink", iconClass: "text-danger" },
} as const;

interface AlertProps {
  tone?: keyof typeof alertTone;
  title?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}

/** Inline banner. Icon + text so color is never the only signal. */
export function Alert({ tone = "info", title, children, action, className }: AlertProps) {
  const { icon: Icon, className: toneClass, iconClass } = alertTone[tone];
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn("flex gap-3 rounded-card border p-4", toneClass, className)}
    >
      <Icon aria-hidden className={cn("mt-0.5 size-5 shrink-0", iconClass)} />
      <div className="flex flex-1 flex-col gap-1 text-small">
        {title && <p className="font-bold">{title}</p>}
        <div className="text-ink-muted">{children}</div>
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  );
}
