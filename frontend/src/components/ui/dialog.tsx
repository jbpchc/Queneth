"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "lucide-react";
import { forwardRef, type ComponentPropsWithoutRef, type ComponentRef, type HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/*
 * Dialogs and sheets on Radix: focus is trapped while open and returned on
 * close, Escape dismisses, and the background is inert (WCAG 2.1.2 / 2.4.3).
 * UX: Flow — never open these during checkout.
 */

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

const Overlay = forwardRef<
  ComponentRef<typeof DialogPrimitive.Overlay>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-[rgb(20_18_20/0.45)] backdrop-blur-[2px]",
      "data-[state=open]:animate-[overlay-in_var(--dur-base)_var(--ease-out)]",
      "data-[state=closed]:animate-[overlay-out_var(--dur-fast)_var(--ease-out)]",
      className,
    )}
    {...props}
  />
));
Overlay.displayName = "DialogOverlay";

function CloseButton() {
  return (
    <DialogPrimitive.Close
      className="absolute right-3 top-3 grid size-11 place-items-center rounded-full text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink"
      aria-label="Close"
    >
      <X aria-hidden className="size-5" />
    </DialogPrimitive.Close>
  );
}

export const DialogContent = forwardRef<
  ComponentRef<typeof DialogPrimitive.Content>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <Overlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 max-h-[calc(100dvh-32px)] w-[calc(100vw-32px)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto",
        "rounded-card border border-border bg-surface p-6 shadow-3 sm:p-8",
        "data-[state=open]:animate-[dialog-in_var(--dur-base)_var(--ease-out)]",
        className,
      )}
      {...props}
    >
      {children}
      <CloseButton />
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
DialogContent.displayName = "DialogContent";

const sheetVariants = cva(
  "fixed z-50 flex flex-col gap-4 overflow-y-auto border-border bg-surface p-6 shadow-3",
  {
    variants: {
      side: {
        // Mobile filter sheets slide up from the bottom (spec §4, Responsive).
        bottom:
          "inset-x-0 bottom-0 max-h-[88dvh] rounded-t-card border-t pb-[max(24px,env(safe-area-inset-bottom))] data-[state=open]:animate-[sheet-up_var(--dur-base)_var(--ease-out)]",
        right:
          "inset-y-0 right-0 h-full w-[min(440px,100vw)] border-l data-[state=open]:animate-[sheet-left_var(--dur-base)_var(--ease-out)]",
        left: "inset-y-0 left-0 h-full w-[min(360px,90vw)] border-r data-[state=open]:animate-[sheet-right_var(--dur-base)_var(--ease-out)]",
      },
    },
    defaultVariants: { side: "right" },
  },
);

export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

export const SheetContent = forwardRef<
  ComponentRef<typeof DialogPrimitive.Content>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & VariantProps<typeof sheetVariants>
>(({ className, side, children, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <Overlay />
    <DialogPrimitive.Content ref={ref} className={cn(sheetVariants({ side }), className)} {...props}>
      {side === "bottom" && (
        <span aria-hidden className="mx-auto -mt-2 mb-1 h-1.5 w-10 rounded-pill bg-border-strong/50" />
      )}
      {children}
      <CloseButton />
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
SheetContent.displayName = "SheetContent";

export function DialogHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1.5 pr-10", className)} {...props} />;
}

export function DialogFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end", className)}
      {...props}
    />
  );
}

export const DialogTitle = forwardRef<
  ComponentRef<typeof DialogPrimitive.Title>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title ref={ref} className={cn("text-h3 font-display text-ink", className)} {...props} />
));
DialogTitle.displayName = "DialogTitle";

export const DialogDescription = forwardRef<
  ComponentRef<typeof DialogPrimitive.Description>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description ref={ref} className={cn("text-small text-ink-muted", className)} {...props} />
));
DialogDescription.displayName = "DialogDescription";
