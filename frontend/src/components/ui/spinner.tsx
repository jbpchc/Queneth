import { LoaderCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export function Spinner({ className, label = "Loading" }: { className?: string; label?: string }) {
  return (
    <span role="status" className={cn("inline-flex", className)}>
      <LoaderCircle aria-hidden className="size-[1.15em] motion-safe:animate-spin" />
      <span className="sr-only">{label}</span>
    </span>
  );
}
