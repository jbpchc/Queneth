"use client";

import { KeyRound, Landmark, Plus, Ticket } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PinInput } from "@/components/wallet/pin-input";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { formatQc } from "@/lib/format";
import { newKey, usePin, useRedeem, useTopUp, useWithdraw, type WalletSummary } from "@/lib/wallet";

/** "Load credits": preset amounts only, daily cap, clearly simulated. No card fields of any kind. */
export function TopUpDialog({ wallet, open, onOpenChange }: { wallet: WalletSummary; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [amount, setAmount] = useState<number | null>(null);
  // One key per attempt: a double tap or a retry can never load credits twice.
  const [key, setKey] = useState(newKey);
  const topup = useTopUp();
  const remaining = wallet.topup_remaining_today_qc;

  async function confirm() {
    if (!amount) return;
    try {
      const res = await topup.mutateAsync({ amount, key });
      toast.success(`${formatQc(amount)} loaded`, { description: `New balance ${formatQc(res.wallet.balance_qc)}` });
      setKey(newKey());
      setAmount(null);
      onOpenChange(false);
    } catch (err) {
      toast.error("Couldn't load credits", { description: toApiError(err).message });
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) topup.reset(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Load credits</DialogTitle>
          <DialogDescription>Choose an amount. You can load up to {formatQc(wallet.daily_topup_cap_qc)} a day.</DialogDescription>
        </DialogHeader>
        <Alert tone="info" className="mt-4">
          Simulated top-up. QueWallet credits are simulated for academic purposes and have no cash value. No payment details are ever asked for.
        </Alert>
        <div role="group" aria-label="Amount" className="mt-5 grid grid-cols-3 gap-2">
          {wallet.topup_presets_qc.map((p) => (
            <Chip key={p} selected={amount === p} disabled={p > remaining} onClick={() => setAmount(p)} className="h-14 text-body">
              {formatQc(p)}
            </Chip>
          ))}
        </div>
        <p className="tabular mt-3 text-small text-ink-muted" aria-live="polite">
          {remaining > 0 ? `${formatQc(remaining)} left today` : "You've reached today's limit. Try again tomorrow, or redeem a code."}
        </p>
        <DialogFooter>
          <Button variant="wallet" size="lg" block disabled={!amount} loading={topup.isPending} onClick={confirm} className="shimmer">
            <Plus aria-hidden /> {amount ? `Load ${formatQc(amount)}` : "Choose an amount"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function RedeemForm() {
  const [code, setCode] = useState("");
  const redeem = useRedeem();
  const error = redeem.error ? toApiError(redeem.error).message : undefined;
  return (
    <form
      className="flex flex-col gap-3 sm:flex-row sm:items-start"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!code.trim()) return;
        try {
          const res = await redeem.mutateAsync(code);
          toast.success("Code redeemed", { description: `${formatQc(res.transaction.amount_qc)} added to your wallet.` });
          setCode("");
        } catch {
          /* shown inline */
        }
      }}
    >
      <Field label="Redeem a code" hint="Spaces and lowercase are fine." error={error} className="flex-1">
        <Input value={code} onChange={(e) => { setCode(e.target.value); redeem.reset(); }} placeholder="QUE-DEMO-5000" autoCapitalize="characters" />
      </Field>
      <Button type="submit" variant="outline" size="lg" loading={redeem.isPending} className="sm:mt-7">
        <Ticket aria-hidden /> Redeem
      </Button>
    </form>
  );
}

export function PinDialog({ hasPin, open, onOpenChange }: { hasPin: boolean; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const { setPin, changePin } = usePin();
  const busy = setPin.isPending || changePin.isPending;

  function reset() {
    setCurrent("");
    setNext("");
    setConfirmPin("");
    setProblem(null);
  }

  async function save() {
    if (next.length !== 6) return setProblem("Your new PIN needs 6 digits.");
    if (next !== confirmPin) return setProblem("The two new PINs don't match.");
    try {
      if (hasPin) await changePin.mutateAsync({ current, next });
      else await setPin.mutateAsync(next);
      toast.success(hasPin ? "PIN changed" : "PIN set", { description: "You'll use it to confirm payments." });
      reset();
      onOpenChange(false);
    } catch (err) {
      setProblem(toApiError(err).message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) reset(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{hasPin ? "Change your PIN" : "Set your QueWallet PIN"}</DialogTitle>
          <DialogDescription>Six digits you'll enter to confirm every payment. Five wrong tries lock the wallet for 15 minutes.</DialogDescription>
        </DialogHeader>
        <div className="mt-5 flex flex-col gap-5">
          {hasPin && <PinInput label="Current PIN" value={current} onChange={setCurrent} autoFocus />}
          <PinInput label="New PIN" value={next} onChange={setNext} autoFocus={!hasPin} />
          <PinInput label="Confirm new PIN" value={confirmPin} onChange={setConfirmPin} invalid={confirmPin.length === 6 && confirmPin !== next} />
          {problem && <p role="alert" className="text-small text-danger">{problem}</p>}
        </div>
        <DialogFooter>
          <Button variant="secondary" size="lg" loading={busy} onClick={save} disabled={next.length < 6 || confirmPin.length < 6 || (hasPin && current.length < 6)}>
            <KeyRound aria-hidden /> {hasPin ? "Change PIN" : "Set PIN"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function WithdrawDialog({ wallet, open, onOpenChange }: { wallet: WalletSummary; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [amount, setAmount] = useState("");
  const [pin, setPin] = useState("");
  const [key, setKey] = useState(newKey);
  const withdraw = useWithdraw();
  const value = Number(amount.replace(/[^\d]/g, "")) || 0; // Postel: "12,500"
  const error = withdraw.error ? toApiError(withdraw.error).message : undefined;

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) { withdraw.reset(); setPin(""); } }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Withdraw earnings</DialogTitle>
          <DialogDescription>A simulated payout to your bank. Available: {formatQc(wallet.available_qc)}.</DialogDescription>
        </DialogHeader>
        <div className="mt-5 flex flex-col gap-5">
          <Field label="Amount (QC)">
            <Input inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="e.g. 10,000" />
          </Field>
          <PinInput label="QueWallet PIN" value={pin} onChange={setPin} invalid={!!error} />
          {error && <p role="alert" className="text-small text-danger">{error}</p>}
        </div>
        <DialogFooter>
          <Button
            variant="secondary"
            size="lg"
            disabled={value < 100 || pin.length < 6}
            loading={withdraw.isPending}
            onClick={async () => {
              try {
                await withdraw.mutateAsync({ amount: value, pin, key });
                toast.success("Payout requested", { description: `${formatQc(value)} is on its way (simulated).` });
                setKey(newKey());
                setAmount("");
                setPin("");
                onOpenChange(false);
              } catch {
                setPin("");
              }
            }}
          >
            <Landmark aria-hidden /> Withdraw {value >= 100 ? formatQc(value) : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
