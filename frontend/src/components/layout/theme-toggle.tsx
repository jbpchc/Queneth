"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const order = ["light", "dark", "system"] as const;
const meta = {
  light: { icon: Sun, label: "Light theme" },
  dark: { icon: Moon, label: "Dark theme" },
  system: { icon: Monitor, label: "System theme" },
} as const;

/** Manual light / dark / system toggle (spec §12 Accessibility). */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const current = (mounted && (theme as (typeof order)[number])) || "system";
  const next = order[(order.indexOf(current) + 1) % order.length]!;
  const Icon = meta[current].icon;

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={`${meta[current].label}. Switch to ${meta[next].label.toLowerCase()}`}
      title={meta[current].label}
      className={cn(
        "grid size-11 place-items-center rounded-full text-ink transition-colors hover:bg-surface-muted",
        className,
      )}
    >
      <Icon aria-hidden className="size-5" />
    </button>
  );
}
