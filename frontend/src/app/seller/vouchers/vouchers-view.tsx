"use client";

import { Pause, Play, Plus, Tag, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, EmptyState, ErrorState } from "@/components/ui/states";
import { fieldErrors, toApiError } from "@/lib/api/client";
import { formatQc } from "@/lib/format";
import { useStudioVouchers, useVoucherActions, type StudioVoucher } from "@/lib/studio";
import { cn } from "@/lib/utils";

const STATE = {
  active: { label: "Active", tone: "success" },
  scheduled: { label: "Scheduled", tone: "info" },
  paused: { label: "Paused", tone: "neutral" },
  expired: { label: "Expired", tone: "neutral" },
  used_up: { label: "Fully claimed", tone: "neutral" },
} as const;
const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium" });

/** Seller-funded vouchers: the discount comes off this boutique's payout. */
export function VouchersView() {
  const vouchers = useStudioVouchers();
  const [creating, setCreating] = useState(false);
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Promotions</p>
          <h1 className="text-h1 text-ink">Discount codes</h1>
          <p className="text-small text-ink-muted">Seller-funded: discounts come off your boutique&apos;s part of the order. One voucher per boutique per bag.</p>
        </div>
        {!creating && <Button variant="primary" onClick={() => setCreating(true)}><Plus aria-hidden /> New voucher</Button>}
      </header>
      {creating && <VoucherForm onDone={() => setCreating(false)} />}
      {vouchers.isPending ? (
        <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading vouchers">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-20 rounded-card" />)}</div>
      ) : vouchers.isError ? (
        <ErrorState message={toApiError(vouchers.error).message} onRetry={() => vouchers.refetch()} />
      ) : vouchers.data.length === 0 ? (
        !creating && <EmptyState icon={Tag} title="No vouchers yet" description="Reward loyal shoppers with a percent or fixed-QC discount, with limits and dates you control." action={<Button variant="primary" onClick={() => setCreating(true)}>New voucher</Button>} />
      ) : (
        <ul className="flex flex-col gap-3">{vouchers.data.map((v) => <VoucherRow key={v.id} v={v} />)}</ul>
      )}
    </div>
  );
}

function VoucherRow({ v }: { v: StudioVoucher }) {
  const { update, remove } = useVoucherActions();
  const s = STATE[v.state];
  const pct = Math.min(100, Math.round((v.used_count / v.max_uses) * 100));
  return (
    <li>
      <Card className="flex flex-wrap items-center gap-4 p-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="tabular rounded-input border border-dashed border-border-strong px-2 py-0.5 font-bold tracking-[0.06em] text-ink">{v.code}</span>
            <Badge tone={s.tone} withIcon={false}>{s.label}</Badge>
          </div>
          <span className="text-small text-ink">
            {v.type === "percent" ? `${v.value}% off` : `${formatQc(v.value)} off`}
            {v.min_spend_qc > 0 && ` from ${formatQc(v.min_spend_qc)}`}
            {v.ends_at && <span className="text-ink-muted"> · until {dateFmt.format(new Date(v.ends_at))}</span>}
          </span>
          {v.description && <span className="text-caption text-ink-muted">{v.description}</span>}
        </div>
        <div className="flex w-44 flex-col gap-1 text-caption text-ink-muted">
          <span className="tabular">{v.used_count}/{v.max_uses} used · {formatQc(v.discount_given_qc)} given</span>
          <div className="h-1.5 rounded-pill bg-surface-muted"><div className="h-1.5 rounded-pill bg-accent-2" style={{ width: `${pct}%` }} /></div>
        </div>
        <div className="flex">
          <Button size="icon" variant="ghost" aria-label={v.is_active ? `Pause ${v.code}` : `Resume ${v.code}`}
            onClick={() => update.mutate({ id: v.id, body: { is_active: !v.is_active } }, { onError: (e) => toast.error(toApiError(e).message) })}>
            {v.is_active ? <Pause aria-hidden /> : <Play aria-hidden />}
          </Button>
          <Button size="icon" variant="ghost" aria-label={`Delete ${v.code}`} className="text-ink-muted hover:text-danger"
            onClick={() => remove.mutate(v.id, { onSuccess: () => toast.success(`${v.code} deleted`), onError: (e) => toast.error(toApiError(e).message) })}>
            <Trash2 aria-hidden />
          </Button>
        </div>
      </Card>
    </li>
  );
}

function VoucherForm({ onDone }: { onDone: () => void }) {
  const { create } = useVoucherActions();
  const [code, setCode] = useState("");
  const [type, setType] = useState<"percent" | "fixed">("percent");
  const [value, setValue] = useState("10");
  const [minSpend, setMinSpend] = useState("");
  const [maxUses, setMaxUses] = useState("100");
  const [ends, setEnds] = useState("");
  const [description, setDescription] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErrors({});
    setError(null);
    try {
      const v = await create.mutateAsync({
        code,
        type,
        value: Number(value) || 0,
        min_spend_qc: Number(minSpend.replace(/\D/g, "")) || 0,
        max_uses: Number(maxUses) || 1,
        ends_at: ends ? new Date(`${ends}T23:59:59`).toISOString() : null,
        description: description || null,
      });
      toast.success(`${v.code} is live`);
      onDone();
    } catch (err) {
      const api = toApiError(err);
      const f = fieldErrors(api);
      if (api.code === "voucher_code_taken") setErrors({ code: api.message });
      else if (Object.keys(f).length) setErrors(f);
      else setError(api.message);
    }
  };

  return (
    <Card className="p-6">
      <form onSubmit={submit} noValidate className="flex flex-col gap-5">
        <h2 className="text-h3 text-ink">New voucher</h2>
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Code" error={errors.code} hint="Letters, digits, dashes. Shoppers type this.">
            <Input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} maxLength={24} placeholder="MIRA15" className="uppercase" />
          </Field>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-small font-semibold text-ink">Type</legend>
            <div className="flex gap-2">
              {(["percent", "fixed"] as const).map((t) => (
                <button key={t} type="button" aria-pressed={type === t} onClick={() => setType(t)}
                  className={cn("h-11 flex-1 rounded-pill border px-4 text-small font-semibold", type === t ? "border-ink bg-ink text-bg" : "border-border-strong")}>
                  {t === "percent" ? "Percent off" : "QC off"}
                </button>
              ))}
            </div>
          </fieldset>
          <Field label={type === "percent" ? "Percent (1–90)" : "Amount (QC)"} error={errors.value}>
            <Input inputMode="numeric" value={value} onChange={(e) => setValue(e.target.value.replace(/\D/g, ""))} />
          </Field>
          <Field label="Minimum spend (QC)" optional hint="Of your boutique's items in the bag.">
            <Input inputMode="numeric" value={minSpend} onChange={(e) => setMinSpend(e.target.value)} placeholder="0" />
          </Field>
          <Field label="Total uses" hint="Each shopper can use it once.">
            <Input inputMode="numeric" value={maxUses} onChange={(e) => setMaxUses(e.target.value.replace(/\D/g, ""))} />
          </Field>
          <Field label="Ends" optional><Input type="date" value={ends} onChange={(e) => setEnds(e.target.value)} /></Field>
        </div>
        <Field label="Note for shoppers" optional><Input value={description} maxLength={160} onChange={(e) => setDescription(e.target.value)} placeholder="15% off the rainy-season edit" /></Field>
        <div className="flex gap-3">
          <Button type="submit" variant="primary" loading={create.isPending}>Create voucher</Button>
          <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}
