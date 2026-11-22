"use client";

import { PackageCheck, Undo2, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { toApiError } from "@/lib/api/client";
import { useOrderActions, type SubOrder } from "@/lib/commerce";
import { formatQc } from "@/lib/format";

const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium" });

type Panel = "cancel" | "received" | "return" | null;

/**
 * What the buyer can do with one boutique's part of the order, right now.
 * UX: Hick's Law — only the actions that apply are shown (cancel before
 * shipping; received or return after delivery).
 * UX: Fitts's Law — the confirm button sits right under the question, and the
 * destructive action is never the default.
 * No modal: the confirmation opens inline so the order stays in view.
 */
export function SubOrderActions({ orderId, sub }: { orderId: string; sub: SubOrder }) {
  const { cancel, received, requestReturn } = useOrderActions(orderId);
  const [panel, setPanel] = useState<Panel>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (sub.actions.length === 0) {
    if (sub.status === "RETURN_REQUESTED") {
      return <p className="text-small text-ink-muted">Return requested. {sub.boutique.name} will reply soon; your QC stays in escrow meanwhile.</p>;
    }
    return null;
  }

  const run = async (fn: () => Promise<unknown>, success: string) => {
    setError(null);
    try {
      await fn();
      toast.success(success);
      setPanel(null);
      setReason("");
    } catch (err) {
      setError(toApiError(err).message);
    }
  };
  const open = (p: Panel) => {
    setPanel(p);
    setError(null);
    setReason("");
  };

  return (
    <div className="flex flex-col gap-3">
      {sub.auto_release_at && (
        <p className="text-small text-ink-muted">
          All good? Mark it received. Otherwise escrow releases to {sub.boutique.name} on{" "}
          <span className="font-semibold text-ink">{dateFmt.format(new Date(sub.auto_release_at))}</span>
          {sub.return_deadline && sub.actions.includes("return") && <> — returns are open until then.</>}
        </p>
      )}
      {panel === null && (
        <div className="flex flex-wrap gap-2">
          {sub.actions.includes("received") && (
            <Button variant="primary" onClick={() => open("received")}>
              <PackageCheck aria-hidden /> I received it
            </Button>
          )}
          {sub.actions.includes("return") && (
            <Button variant="outline" onClick={() => open("return")}>
              <Undo2 aria-hidden /> Request a return
            </Button>
          )}
          {sub.actions.includes("cancel") && (
            <Button variant="danger" onClick={() => open("cancel")}>
              <X aria-hidden /> Cancel this part
            </Button>
          )}
        </div>
      )}

      {panel === "received" && (
        <Confirm
          title="Everything arrived as described?"
          body={`This releases ${formatQc(sub.subtotal_qc)} from escrow to ${sub.boutique.name} and adds your Que Points. It can't be undone.`}
          confirmLabel="Yes, I received it"
          loading={received.isPending}
          onConfirm={() => run(() => received.mutateAsync(sub.id), "Thank you! Your Que Points are in.")}
          onBack={() => setPanel(null)}
          error={error}
        />
      )}
      {panel === "cancel" && (
        <Confirm
          title={`Cancel ${sub.number}?`}
          body={`${formatQc(sub.subtotal_qc)} goes straight back to your QueWallet. Other boutiques in this order aren't affected.`}
          confirmLabel="Cancel and refund"
          danger
          loading={cancel.isPending}
          onConfirm={() => run(() => cancel.mutateAsync({ subId: sub.id, reason }), "Cancelled. Your QC is back in your wallet.")}
          onBack={() => setPanel(null)}
          error={error}
        >
          <label className="flex flex-col gap-1.5 text-small">
            <span className="font-semibold text-ink">Reason <span className="font-normal text-ink-muted">(optional, helps the boutique)</span></span>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value.slice(0, 300))} rows={2} />
          </label>
        </Confirm>
      )}
      {panel === "return" && (
        <Confirm
          title="What's wrong with it?"
          body={`${sub.boutique.name} reviews your request. If approved, ${formatQc(sub.subtotal_qc)} is refunded to your QueWallet.`}
          confirmLabel="Send return request"
          loading={requestReturn.isPending}
          disabled={reason.trim().length < 10}
          onConfirm={() => run(() => requestReturn.mutateAsync({ subId: sub.id, reason }), "Return requested. We've told the boutique.")}
          onBack={() => setPanel(null)}
          error={error}
        >
          <label className="flex flex-col gap-1.5 text-small">
            <span className="font-semibold text-ink">Reason</span>
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value.slice(0, 500))}
              rows={3}
              placeholder="e.g. The silk has a pulled thread near the hem."
              aria-describedby="return-hint"
            />
            <span id="return-hint" className="text-caption text-ink-muted">At least 10 characters · {reason.trim().length}/500</span>
          </label>
        </Confirm>
      )}
    </div>
  );
}

function Confirm({
  title,
  body,
  confirmLabel,
  danger,
  loading,
  disabled,
  onConfirm,
  onBack,
  error,
  children,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  danger?: boolean;
  loading: boolean;
  disabled?: boolean;
  onConfirm: () => void;
  onBack: () => void;
  error: string | null;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-input border border-border-strong p-4" role="group" aria-label={title}>
      <p className="font-semibold text-ink">{title}</p>
      <p className="text-small text-ink-muted">{body}</p>
      {children}
      {error && <p role="alert" className="text-small text-danger">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant={danger ? "danger" : "primary"} loading={loading} disabled={disabled} onClick={onConfirm}>
          {confirmLabel}
        </Button>
        <Button variant="ghost" onClick={onBack}>Go back</Button>
      </div>
    </div>
  );
}
