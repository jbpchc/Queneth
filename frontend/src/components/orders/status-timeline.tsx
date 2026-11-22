import { Check, CircleX, PackageCheck, RotateCcw, Truck, Undo2 } from "lucide-react";

import type { SubOrder } from "@/lib/commerce";
import { cn } from "@/lib/utils";

const MAIN = [
  { status: "PAID", label: "Paid" },
  { status: "PROCESSING", label: "Preparing" },
  { status: "SHIPPED", label: "Shipped" },
  { status: "DELIVERED", label: "Delivered" },
  { status: "COMPLETED", label: "Completed" },
] as const;

const BRANCH: Record<string, { label: string; tone: "danger" | "warning" | "neutral"; icon: typeof CircleX }> = {
  CANCELLED: { label: "Cancelled", tone: "neutral", icon: CircleX },
  RETURN_REQUESTED: { label: "Return requested", tone: "warning", icon: Undo2 },
  REFUNDED: { label: "Refunded", tone: "neutral", icon: RotateCcw },
};

const dateFmt = new Intl.DateTimeFormat("en-PH", { month: "short", day: "numeric" });
const fullFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" });

/**
 * Where one boutique's part of the order is.
 * UX: Goal-Gradient — the filled track shows how close the parcel is to you.
 * UX: Common Region — each step's date sits under its own dot; detours
 * (cancelled, return) branch off where they happened, so nothing is hidden.
 */
export function StatusTimeline({ sub }: { sub: Pick<SubOrder, "status" | "events"> }) {
  const reached = new Map<string, string>();
  for (const e of sub.events) reached.set(e.to_status, e.created_at);
  const branch = BRANCH[sub.status];
  // The main track stops where a detour started.
  const lastMainIndex = MAIN.reduce((acc, s, i) => (reached.has(s.status) ? i : acc), 0);
  const steps = branch ? MAIN.slice(0, lastMainIndex + 1) : MAIN;
  // The line after a step: filled when the next step (or the detour) was reached.
  const connectorAfter = (i: number) => {
    const last = i === steps.length - 1;
    if (last) return branch ? "bg-border" : "invisible";
    return reached.has(steps[i + 1]!.status) ? "bg-success" : "bg-border";
  };

  return (
    <div className="flex flex-col gap-4">
      <ol className="flex items-start" aria-label="Order progress">
        {steps.map((s, i) => {
          const at = reached.get(s.status);
          const done = !!at;
          const current = done && (i === lastMainIndex) && !branch && sub.status === s.status;
          return (
            <li key={s.status} className="flex min-w-0 flex-1 flex-col items-center gap-1.5 text-center last:flex-none" aria-current={current ? "step" : undefined}>
              <div className="flex w-full items-center">
                <span className={cn("h-0.5 flex-1", i === 0 ? "invisible" : done ? "bg-success" : "bg-border")} aria-hidden />
                <span
                  className={cn(
                    "grid size-7 shrink-0 place-items-center rounded-full border-2 text-caption",
                    done ? "border-success bg-success text-bg" : "border-border bg-surface text-ink-muted",
                    current && "ring-4 ring-success/20",
                  )}
                  aria-hidden
                >
                  {done ? stepIcon(s.status) : i + 1}
                </span>
                <span className={cn("h-0.5 flex-1", connectorAfter(i))} aria-hidden />
              </div>
              <span className={cn("text-caption font-semibold", done ? "text-ink" : "text-ink-muted")}>{s.label}</span>
              <span className="tabular text-caption text-ink-muted">{at ? dateFmt.format(new Date(at)) : "—"}</span>
              <span className="sr-only">{done ? `done on ${fullFmt.format(new Date(at!))}` : "not yet"}</span>
            </li>
          );
        })}
        {branch && (
          <li className="flex min-w-0 flex-col items-center gap-1.5 text-center" aria-current="step">
            <span
              className={cn(
                "grid size-7 place-items-center rounded-full border-2",
                branch.tone === "warning" ? "border-warning bg-warning text-bg" : "border-ink-muted bg-ink-muted text-bg",
              )}
              aria-hidden
            >
              <branch.icon className="size-4" />
            </span>
            <span className="text-caption font-semibold text-ink">{branch.label}</span>
            <span className="tabular text-caption text-ink-muted">
              {reached.get(sub.status) ? dateFmt.format(new Date(reached.get(sub.status)!)) : "—"}
            </span>
          </li>
        )}
      </ol>

      <details className="group rounded-input bg-surface-muted/60 px-4 py-2 text-small">
        <summary className="flex min-h-11 cursor-pointer items-center font-semibold text-ink">
          Activity ({sub.events.length})
        </summary>
        <ol className="flex flex-col gap-3 pb-3">
          {[...sub.events].reverse().map((e, i) => (
            <li key={`${e.to_status}-${i}`} className="flex flex-col">
              <span className="font-semibold text-ink">
                {labelFor(e.to_status)}
                <span className="ml-2 font-normal text-ink-muted">{fullFmt.format(new Date(e.created_at))}</span>
              </span>
              {e.note && <span className="text-ink-muted">{e.note}</span>}
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}

function stepIcon(status: string) {
  if (status === "SHIPPED") return <Truck className="size-3.5" />;
  if (status === "DELIVERED") return <PackageCheck className="size-3.5" />;
  return <Check className="size-3.5" />;
}

function labelFor(status: string): string {
  return MAIN.find((s) => s.status === status)?.label ?? BRANCH[status]?.label ?? status;
}
