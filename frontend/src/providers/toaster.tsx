"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner } from "sonner";

/** Toasts slide in bottom-center on mobile (above the tab bar), bottom-right on desktop. */
export function Toaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Sonner
      theme={resolvedTheme === "dark" ? "dark" : "light"}
      position="bottom-right"
      offset={24}
      mobileOffset={{ bottom: 88 }}
      toastOptions={{
        classNames: {
          toast:
            "!rounded-card !border !border-border !bg-surface !text-ink !shadow-3 !font-sans",
          description: "!text-ink-muted",
          actionButton: "!rounded-pill !bg-ink !text-bg !font-semibold",
          cancelButton: "!rounded-pill !bg-surface-muted !text-ink",
        },
      }}
    />
  );
}
