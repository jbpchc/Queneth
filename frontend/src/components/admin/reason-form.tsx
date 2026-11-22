"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { toApiError } from "@/lib/api/client";

/**
 * Inline "why?" step before an audited admin action (ban, suspend, reject,
 * reverse…). UX: Fitts's Law — confirm sits right under the question; the
 * destructive variant is never the default focus.
 */
export function ReasonForm({
  label,
  confirmLabel,
  danger,
  min = 5,
  optional,
  placeholder,
  onSubmit,
  onCancel,
}: {
  label: string;
  confirmLabel: string;
  danger?: boolean;
  min?: number;
  optional?: boolean;
  placeholder?: string;
  onSubmit: (reason: string) => Promise<unknown>;
  onCancel: () => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ok = optional || text.trim().length >= min;
  return (
    <div className="flex flex-col gap-2 rounded-input border border-border-strong bg-surface p-3" role="group" aria-label={label}>
      <label className="flex flex-col gap-1.5 text-small">
        <span className="font-semibold text-ink">{label}{optional && <span className="font-normal text-ink-muted"> (optional)</span>}</span>
        <Textarea rows={2} value={text} maxLength={500} placeholder={placeholder} onChange={(e) => setText(e.target.value)} autoFocus />
        {!optional && <span className="text-caption text-ink-muted">Recorded in the audit log · at least {min} characters</span>}
      </label>
      {error && <p role="alert" className="text-small text-danger">{error}</p>}
      <div className="flex gap-2">
        <Button
          size="sm"
          variant={danger ? "danger" : "primary"}
          disabled={!ok}
          loading={busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              await onSubmit(text.trim());
            } catch (err) {
              setError(toApiError(err).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {confirmLabel}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}
