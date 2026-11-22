import { cva, type VariantProps } from "class-variance-authority";
import { CircleAlert, CircleCheck, CircleX, Info } from "lucide-react";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * Small pill labels. Pops (citrus/tangerine/lilac) always carry ink text.
 * UX: Von Restorff effect — citrus "New drop" / "Last 2 left" badges are used
 * sparingly and only when true (no fake scarcity).
 */
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-pill px-2.5 py-0.5 text-caption font-bold uppercase tracking-[0.06em] [&_svg]:size-3.5",
  {
    variants: {
      tone: {
        neutral: "bg-surface-muted text-ink",
        ink: "bg-ink text-bg",
        citrus: "bg-citrus text-on-pop",
        tangerine: "bg-tangerine text-on-pop",
        lilac: "bg-lilac text-on-pop",
        success: "bg-success-soft text-success",
        warning: "bg-warning-soft text-warning",
        danger: "bg-danger-soft text-danger",
        info: "bg-accent-2/10 text-accent-2",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

const statusIcon = {
  success: CircleCheck,
  warning: CircleAlert,
  danger: CircleX,
  info: Info,
} as const;

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /** Accessibility: status tones show an icon so color is never the only signal. */
  withIcon?: boolean;
}

export function Badge({ className, tone, withIcon = true, children, ...props }: BadgeProps) {
  const Icon = tone && tone in statusIcon ? statusIcon[tone as keyof typeof statusIcon] : null;
  return (
    <span className={cn(badgeVariants({ tone }), className)} {...props}>
      {withIcon && Icon && <Icon aria-hidden />}
      {children}
    </span>
  );
}
