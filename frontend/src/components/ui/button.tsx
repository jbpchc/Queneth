import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

import { Spinner } from "./spinner";

/**
 * The single button system (Gestalt: Similarity — every button of a kind looks
 * the same everywhere). Pills, press-scale to 0.97, brand easing.
 *
 * UX: Von Restorff effect — `primary` (Que Magenta) is reserved for ONE call to
 * action per view. Everything else uses `secondary`, `outline` or `ghost`.
 */
export const buttonVariants = cva(
  [
    "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap",
    "rounded-pill font-semibold tracking-[0.01em]",
    "transition-[background-color,color,box-shadow,transform,border-color] duration-[var(--dur-fast)] ease-brand",
    "motion-safe:active:scale-[0.97] motion-safe:active:duration-[var(--dur-instant)]",
    "disabled:pointer-events-none disabled:opacity-45",
    "[&_svg]:size-[1.15em] [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary: "bg-accent text-on-accent shadow-1 hover:bg-accent-hover hover:shadow-2",
        secondary: "bg-ink text-bg hover:bg-ink/85",
        outline: "border border-border-strong bg-transparent text-ink hover:bg-surface-muted",
        ghost: "bg-transparent text-ink hover:bg-surface-muted",
        wallet: "bg-accent-2 text-on-accent-2 shadow-1 hover:bg-accent-2-hover hover:shadow-2",
        danger:
          "border border-danger/40 bg-transparent text-danger hover:border-danger hover:bg-danger-soft",
        link: "rounded-none text-accent-2 underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-9 px-4 text-small",
        // UX: Fitts's Law — default and large buttons meet the 44px / 48px target sizes.
        md: "h-11 px-5 text-small",
        lg: "h-12 px-7 text-body",
        icon: "size-11 p-0",
      },
      block: { true: "w-full", false: "" },
    },
    compoundVariants: [{ variant: "link", className: "h-auto px-0" }],
    defaultVariants: { variant: "secondary", size: "md", block: false },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      block,
      asChild = false,
      loading = false,
      disabled,
      type,
      children,
      ...props
    },
    ref,
  ) => {
    const classes = cn(buttonVariants({ variant, size, block }), className);
    if (asChild) {
      return (
        <Slot ref={ref} className={classes} {...props}>
          {children}
        </Slot>
      );
    }
    return (
      <button
        ref={ref}
        type={type ?? "button"}
        className={classes}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...props}
      >
        {loading && <Spinner className="absolute" label="Working" />}
        <span className={cn("inline-flex items-center gap-2", loading && "invisible")}>
          {children}
        </span>
      </button>
    );
  },
);
Button.displayName = "Button";
