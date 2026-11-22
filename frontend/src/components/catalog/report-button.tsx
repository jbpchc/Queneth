"use client";

import { Flag } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api, toApiError, type ApiSchemas } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { cn } from "@/lib/utils";

type Reason = ApiSchemas["ReportIn"]["reason"];
const REASONS: { value: Reason; label: string }[] = [
  { value: "counterfeit", label: "Looks counterfeit" },
  { value: "misleading", label: "Misleading" },
  { value: "offensive", label: "Offensive" },
  { value: "spam", label: "Spam" },
  { value: "other", label: "Something else" },
];

/**
 * Report a product or review to the moderation team.
 * UX: Hick's Law — five plain reasons; the note is optional.
 * UX: Selective Attention — a quiet text link, never competing with buying.
 */
export function ReportButton({ type, id, label }: { type: "product" | "review"; id: string; label?: string }) {
  const { status } = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<Reason | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async () => {
    if (!reason) return;
    setBusy(true);
    try {
      const { error } = await api.POST("/api/v1/reports", { body: { target_type: type, target_id: id, reason, note: note.trim() || null } });
      if (error) throw error;
      setSent(true);
      setOpen(false);
      toast.success("Thanks for letting us know", { description: "Our team reviews every report." });
    } catch (err) {
      toast.error(toApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  if (sent) return <span className="inline-flex items-center gap-1 text-caption text-ink-muted"><Flag aria-hidden className="size-3.5" /> Reported</span>;

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        if (o && status !== "authenticated") {
          toast("Sign in to report", { action: { label: "Sign in", onClick: () => router.push(`/login?next=${encodeURIComponent(location.pathname)}`) } });
          return;
        }
        setOpen(o);
      }}
    >
      <PopoverTrigger asChild>
        <button type="button" className="inline-flex min-h-11 items-center gap-1 text-caption text-ink-muted hover:text-ink hover:underline">
          <Flag aria-hidden className="size-3.5" /> {label ?? (type === "product" ? "Report this piece" : "Report")}
        </button>
      </PopoverTrigger>
      <PopoverContent className="flex w-80 flex-col gap-3" align="start">
        <p className="text-small font-semibold text-ink">What&apos;s wrong with this {type === "product" ? "piece" : "review"}?</p>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Reason">
          {REASONS.map((r) => (
            <button key={r.value} type="button" role="radio" aria-checked={reason === r.value} onClick={() => setReason(r.value)}
              className={cn("min-h-11 rounded-pill border px-3 text-small font-semibold", reason === r.value ? "border-ink bg-ink text-bg" : "border-border-strong text-ink")}>
              {r.label}
            </button>
          ))}
        </div>
        <label className="flex flex-col gap-1 text-small">
          <span className="font-semibold text-ink">Details <span className="font-normal text-ink-muted">(optional)</span></span>
          <Textarea rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <Button variant="primary" size="sm" disabled={!reason} loading={busy} onClick={submit} className="self-start">Send report</Button>
      </PopoverContent>
    </Popover>
  );
}
