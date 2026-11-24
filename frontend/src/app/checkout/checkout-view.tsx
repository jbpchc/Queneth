"use client";

import { Check, Lock, MapPin, Plus, ShieldCheck, ShoppingBag, Store, Wallet } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { AddressForm } from "@/components/account/address-form";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Alert, EmptyState, ErrorState } from "@/components/ui/states";
import { PinInput } from "@/components/wallet/pin-input";
import { toApiError, type ApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { addressLine, formatPhone, useAddresses, useCheckout, type Address } from "@/lib/commerce";
import { formatQc, optionLabel } from "@/lib/format";
import { useBag } from "@/lib/shop";
import { newKey, usePin, useTopUp, useWallet } from "@/lib/wallet";
import { cn } from "@/lib/utils";

type Step = 0 | 1 | 2;
const STEPS = ["Address", "Review", "Pay"] as const;

/**
 * One page, three collapsible steps (Address → Review → Pay), no modals.
 *
 * UX: Goal-Gradient — a progress bar fills as each step is completed.
 * UX: Hick's Law — one open step at a time; finished steps collapse to a summary.
 * UX: Tesler's Law — vouchers, splitting per boutique and escrow are handled by
 *     the server; the buyer only confirms an address, reviews, and enters a PIN.
 * UX: Doherty Threshold — the Pay button shows progress instantly and the
 *     idempotency key makes a double-click or a retry safe.
 */
export function CheckoutView() {
  const router = useRouter();
  const { status, user } = useSession();
  const bag = useBag();
  const wallet = useWallet();
  const addresses = useAddresses();
  const checkout = useCheckout();

  const [step, setStep] = useState<Step>(0);
  const [addressId, setAddressId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [pin, setPin] = useState("");
  const [payError, setPayError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // One key per attempt: a network retry reuses it (never charged twice);
  // a definite answer from the server starts a fresh attempt.
  const attempt = useRef<string>(newKey());

  useEffect(() => {
    if (status === "guest") router.replace("/login?next=/checkout");
  }, [status, router]);

  // Pre-select the default address once addresses arrive.
  useEffect(() => {
    if (addressId || !addresses.data?.length) return;
    setAddressId((addresses.data.find((a) => a.is_default) ?? addresses.data[0])?.id ?? null);
  }, [addresses.data, addressId]);

  const address = useMemo(
    () => addresses.data?.find((a) => a.id === addressId) ?? null,
    [addresses.data, addressId],
  );

  // Paid: the bag is now empty, so hold here while the confirmation opens.
  if (checkout.isSuccess) {
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-center" role="status">
        <Spinner label="Opening your confirmation" />
        <p className="text-body font-semibold text-ink">Payment complete. Opening your confirmation…</p>
      </div>
    );
  }
  if (status !== "authenticated" || bag.isPending || addresses.isPending || wallet.isPending) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading checkout">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-3 w-full rounded-pill" />
        <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
          <Skeleton className="h-80 rounded-card" />
          <Skeleton className="h-64 rounded-card" />
        </div>
      </div>
    );
  }
  const loadError = bag.error ?? addresses.error ?? wallet.error;
  if (loadError || !bag.data || !addresses.data || !wallet.data) {
    return (
      <ErrorState
        message={toApiError(loadError).message}
        onRetry={() => {
          bag.refetch();
          addresses.refetch();
          wallet.refetch();
        }}
      />
    );
  }

  const data = bag.data;
  if (data.groups.length === 0) {
    return (
      <EmptyState
        icon={ShoppingBag}
        title="Your bag is empty"
        description="Add a piece to your bag, then come back to check out."
        action={<Button asChild variant="secondary"><Link href="/search?sort=newest">Browse new arrivals</Link></Button>}
      />
    );
  }
  const unavailable = data.groups.some((g) => g.items.some((i) => !i.available));
  const balance = wallet.data.balance_qc;
  const short = Math.max(0, data.total_qc - balance);
  const canPay = !!address && !unavailable && short === 0 && pin.length === 6 && wallet.data.has_pin;

  const pay = async () => {
    if (!address) return;
    setPayError(null);
    setNotice(null);
    try {
      const order = await checkout.mutateAsync({
        addressId: address.id,
        pin,
        total: data.total_qc,
        key: attempt.current,
      });
      router.replace(`/checkout/success/${order.id}`);
    } catch (err) {
      const e = toApiError(err);
      if (e.code !== "network_error") attempt.current = newKey();
      setPin("");
      if (e.code === "prices_changed") {
        await bag.refetch();
        setNotice("Prices or vouchers changed since you reviewed. Check the new total, then pay.");
        setStep(1);
        return;
      }
      if (e.code === "stock_changed" || e.code === "empty_bag") {
        await bag.refetch();
      }
      if (e.code === "insufficient_funds") await wallet.refetch();
      setPayError(e);
    }
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-4">
        <nav aria-label="Breadcrumb" className="text-small text-ink-muted">
          <Link href="/bag" className="hover:underline">Bag</Link> / Checkout
        </nav>
        <h1 className="text-h1 text-ink">Checkout</h1>
        <Progress
          value={step + 1}
          max={3}
          label={`Step ${step + 1} of 3 · ${STEPS[step]}`}
          showValue={false}
          tone="ink"
        />
      </header>

      {unavailable && (
        <Alert tone="danger" title="Some pieces sold out" action={<Button asChild size="sm" variant="outline"><Link href="/bag">Review bag</Link></Button>}>
          Remove them from your bag to continue.
        </Alert>
      )}

      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <div className="flex min-w-0 flex-col gap-4">
          {/* Step 1 — Address */}
          <StepCard
            index={0}
            current={step}
            title="Delivery address"
            summary={address ? `${address.recipient} · ${addressLine(address)}` : undefined}
            onEdit={() => setStep(0)}
          >
            {addresses.data.length > 0 && !adding && (
              <fieldset className="flex flex-col gap-3">
                <legend className="sr-only">Choose an address</legend>
                {addresses.data.map((a) => (
                  <AddressOption key={a.id} address={a} checked={a.id === addressId} onChange={() => setAddressId(a.id)} />
                ))}
                <Button variant="ghost" className="self-start" onClick={() => setAdding(true)}>
                  <Plus aria-hidden /> Add a new address
                </Button>
              </fieldset>
            )}
            {(adding || addresses.data.length === 0) && (
              <div className="flex flex-col gap-4">
                {addresses.data.length === 0 && (
                  <p className="text-small text-ink-muted">Where should we deliver? We&apos;ll save this for next time.</p>
                )}
                <AddressForm
                  defaultName={user?.name}
                  submitLabel="Save and use this address"
                  onCancel={addresses.data.length ? () => setAdding(false) : undefined}
                  onSaved={(a) => {
                    setAddressId(a.id);
                    setAdding(false);
                  }}
                />
              </div>
            )}
            {!adding && address && (
              <Button variant="secondary" size="lg" className="mt-2 self-start" onClick={() => setStep(1)}>
                Continue to review
              </Button>
            )}
          </StepCard>

          {/* Step 2 — Review */}
          <StepCard
            index={1}
            current={step}
            title="Review your order"
            summary={`${data.item_count} ${data.item_count === 1 ? "piece" : "pieces"} from ${data.groups.length} ${data.groups.length === 1 ? "boutique" : "boutiques"}`}
            onEdit={() => setStep(1)}
          >
            {notice && <Alert tone="warning">{notice}</Alert>}
            <p className="text-small text-ink-muted">
              Each boutique ships separately. Your payment is held in escrow and released to a boutique only after its pieces arrive.
            </p>
            {data.groups.map((g) => (
              <section key={g.boutique.slug} className="flex flex-col gap-3 rounded-input border border-border p-4" aria-label={g.boutique.name}>
                <div className="flex items-center gap-2 text-small">
                  <Store aria-hidden className="size-4 text-ink-muted" />
                  <span className="font-semibold text-ink">{g.boutique.name}</span>
                  <span className="ml-auto tabular font-semibold">{formatQc(g.total_qc)}</span>
                </div>
                <ul className="flex flex-col gap-3">
                  {g.items.map((i) => (
                    <li key={i.id} className="flex items-center gap-3">
                      <div className="relative aspect-[4/5] w-14 shrink-0 overflow-hidden rounded-input bg-surface-muted">
                        {i.product.image && <Image src={i.product.image.url} alt="" fill sizes="56px" className="object-cover" />}
                      </div>
                      <div className="min-w-0 flex-1 text-small">
                        <p className="truncate font-semibold text-ink">{i.product.title}</p>
                        <p className="text-ink-muted">{optionLabel(i.options)} · Qty {i.qty}</p>
                      </div>
                      <span className="tabular text-small">{formatQc(i.line_total_qc)}</span>
                    </li>
                  ))}
                </ul>
                {g.voucher && g.discount_qc > 0 && (
                  <p className="flex justify-between text-small text-success">
                    <span>Voucher {g.voucher.code}</span>
                    <span className="tabular">−{formatQc(g.discount_qc)}</span>
                  </p>
                )}
              </section>
            ))}
            <div className="flex flex-wrap gap-3">
              <Button variant="secondary" size="lg" onClick={() => { setNotice(null); setStep(2); }} disabled={unavailable}>
                Continue to payment
              </Button>
              <Button asChild variant="ghost" size="lg"><Link href="/bag">Edit bag</Link></Button>
            </div>
          </StepCard>

          {/* Step 3 — Pay */}
          <StepCard index={2} current={step} title="Pay with QueWallet">
            <div className="flex items-center justify-between rounded-input bg-surface-muted p-4">
              <span className="flex items-center gap-2 text-small text-ink-muted"><Wallet aria-hidden className="size-4" /> Available balance</span>
              <span className={cn("tabular font-bold", short > 0 ? "text-danger" : "text-ink")}>{formatQc(balance)}</span>
            </div>
            {short > 0 ? (
              <TopUpPanel short={short} presets={wallet.data.topup_presets_qc} remaining={wallet.data.topup_remaining_today_qc} />
            ) : !wallet.data.has_pin ? (
              <CreatePin />
            ) : (
              <>
                <PinInput
                  label="Enter your 6-digit QueWallet PIN"
                  value={pin}
                  onChange={(v) => { setPin(v); setPayError(null); }}
                  invalid={payError?.code === "wrong_pin"}
                  disabled={checkout.isPending || payError?.code === "wallet_locked"}
                  autoFocus
                />
                <p className="flex items-center gap-1.5 text-caption text-ink-muted">
                  <Lock aria-hidden className="size-3.5" /> Your PIN confirms this payment. We never store it in plain text.
                </p>
              </>
            )}
            {payError && <PayError error={payError} />}
          </StepCard>
        </div>

        {/* Summary + the single primary action */}
        <aside className="flex flex-col gap-4 lg:sticky lg:top-24 lg:self-start">
          <Card className="flex flex-col gap-4 p-6">
            <h2 className="text-h3 text-ink">Order total</h2>
            <dl className="flex flex-col gap-2 text-small">
              <div className="flex justify-between"><dt className="text-ink-muted">Items</dt><dd className="tabular">{formatQc(data.subtotal_qc)}</dd></div>
              {data.discount_qc > 0 && (
                <div className="flex justify-between text-success"><dt>Vouchers</dt><dd className="tabular">−{formatQc(data.discount_qc)}</dd></div>
              )}
              <div className="flex justify-between"><dt className="text-ink-muted">Shipping</dt><dd>Included</dd></div>
              <div className="flex justify-between border-t border-border pt-3 text-h3 font-bold"><dt>Total</dt><dd className="tabular">{formatQc(data.total_qc)}</dd></div>
              <div className="flex justify-between text-ink-muted"><dt>Que Points on delivery</dt><dd className="tabular">+{Math.floor(data.total_qc / 100).toLocaleString()}</dd></div>
            </dl>
            <p className="flex items-start gap-2 text-caption text-ink-muted">
              <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-success" />
              Held in escrow until delivery. Refunded to your QueWallet if a boutique can&apos;t ship.
            </p>
          </Card>
          <Alert tone="info">QueWallet credits are simulated for academic purposes and have no cash value.</Alert>
        </aside>
      </div>

      {/* Sticky pay bar — reachable with a thumb on phones (Fitts's Law). */}
      {step === 2 && (
        <div className="sticky bottom-0 z-30 -mx-4 border-t border-border bg-bg/95 px-4 py-4 backdrop-blur sm:-mx-6 sm:px-6">
          <div className="mx-auto flex max-w-6xl flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-end">
            <p className="text-small text-ink-muted sm:mr-auto">
              {address ? <>Delivering to <span className="font-semibold text-ink">{address.label}</span> · {address.city}</> : "Choose an address first"}
            </p>
            <Button
              variant="wallet"
              size="lg"
              className={cn("min-w-72", canPay && !checkout.isPending && "shimmer")}
              disabled={!canPay}
              loading={checkout.isPending}
              onClick={pay}
            >
              <Wallet aria-hidden /> Pay {formatQc(data.total_qc)} with QueWallet
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function StepCard({
  index,
  current,
  title,
  summary,
  onEdit,
  children,
}: {
  index: Step;
  current: Step;
  title: string;
  summary?: string;
  onEdit?: () => void;
  children: ReactNode;
}) {
  const done = index < current;
  const open = index === current;
  return (
    <Card className={cn("flex flex-col gap-4 p-5 sm:p-6", !open && "opacity-90")} aria-current={open ? "step" : undefined}>
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "grid size-8 shrink-0 place-items-center rounded-full text-small font-bold",
            done ? "bg-success text-bg" : open ? "bg-ink text-bg" : "bg-surface-muted text-ink-muted",
          )}
          aria-hidden
        >
          {done ? <Check className="size-4" /> : index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className={cn("text-h3", open || done ? "text-ink" : "text-ink-muted")}>{title}</h2>
          {done && summary && <p className="truncate text-small text-ink-muted">{summary}</p>}
        </div>
        {done && onEdit && (
          <Button variant="ghost" size="sm" onClick={onEdit} aria-label={`Change ${title.toLowerCase()}`}>
            Change
          </Button>
        )}
      </div>
      {open && <div className="flex flex-col gap-4">{children}</div>}
    </Card>
  );
}

function AddressOption({ address: a, checked, onChange }: { address: Address; checked: boolean; onChange: () => void }) {
  return (
    <label
      className={cn(
        "flex cursor-pointer gap-3 rounded-input border p-4 transition-colors",
        checked ? "border-ink bg-surface-muted/60" : "border-border hover:border-border-strong",
      )}
    >
      <input type="radio" name="address" checked={checked} onChange={onChange} className="mt-1 size-4 accent-[var(--accent-2)]" />
      <span className="flex flex-col gap-0.5 text-small">
        <span className="flex items-center gap-2 font-semibold text-ink">
          <MapPin aria-hidden className="size-4 text-ink-muted" /> {a.label}
          {a.is_default && <span className="text-caption font-bold uppercase tracking-[0.08em] text-accent-2">Default</span>}
        </span>
        <span className="text-ink">{a.recipient} · <span className="tabular">{formatPhone(a.phone)}</span></span>
        <span className="text-ink-muted">{addressLine(a)}</span>
      </span>
    </label>
  );
}

/**
 * UX: Tesler's Law — an empty wallet is fixed right here (quick top-up chips),
 * instead of sending the buyer away and losing their place.
 */
function TopUpPanel({ short, presets, remaining }: { short: number; presets: number[]; remaining: number }) {
  const topUp = useTopUp();
  const [error, setError] = useState<string | null>(null);
  // The smallest preset that covers the gap is offered first.
  const options = Array.from(new Set([...presets.filter((p) => p >= short).slice(0, 1), ...presets])).filter((p) => p <= remaining);
  const run = async (amount: number) => {
    setError(null);
    try {
      await topUp.mutateAsync({ amount, key: newKey() });
    } catch (err) {
      setError(toApiError(err).message);
    }
  };
  return (
    <div className="flex flex-col gap-3 rounded-input border border-danger/40 bg-danger-soft/40 p-4" role="status">
      <p className="font-semibold text-ink">Not enough QC — you need {formatQc(short)} more.</p>
      <p className="text-small text-ink-muted">Add simulated credits now; your bag and address stay as they are.</p>
      {options.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {options.map((amt, i) => (
            <Button key={amt} variant={i === 0 && amt >= short ? "wallet" : "outline"} loading={topUp.isPending && topUp.variables?.amount === amt} disabled={topUp.isPending} onClick={() => run(amt)}>
              <Plus aria-hidden /> {formatQc(amt)}
            </Button>
          ))}
        </div>
      ) : (
        <p className="text-small text-danger">You&apos;ve reached today&apos;s top-up limit.</p>
      )}
      <Link href="/account/wallet" className="text-small font-semibold text-accent-2 hover:underline">Redeem a QueWallet code instead</Link>
      {error && <p role="alert" className="text-small text-danger">{error}</p>}
    </div>
  );
}

function CreatePin() {
  const { setPin } = usePin();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="flex flex-col gap-3">
      <Alert tone="info" title="Set your QueWallet PIN">You&apos;ll use these six digits to confirm every payment.</Alert>
      <PinInput label="Choose a 6-digit PIN" value={value} onChange={setValue} autoFocus invalid={!!error} />
      <Button
        variant="secondary"
        className="self-start"
        disabled={value.length !== 6}
        loading={setPin.isPending}
        onClick={async () => {
          setError(null);
          try {
            await setPin.mutateAsync(value);
          } catch (err) {
            setError(toApiError(err).message);
          }
        }}
      >
        Save PIN
      </Button>
      {error && <p role="alert" className="text-small text-danger">{error}</p>}
    </div>
  );
}

function PayError({ error }: { error: ApiError }) {
  if (error.code === "stock_changed") {
    return (
      <Alert tone="danger" title="Some pieces just sold out" action={<Button asChild size="sm" variant="outline"><Link href="/bag">Review bag</Link></Button>}>
        {error.message} You haven&apos;t been charged.
      </Alert>
    );
  }
  if (error.code === "wallet_locked") {
    return <Alert tone="danger" title="Wallet locked">{error.message} You haven&apos;t been charged.</Alert>;
  }
  if (error.code === "wrong_pin") {
    return <p role="alert" className="text-small font-semibold text-danger">{error.message}</p>;
  }
  return <Alert tone="danger" title="Payment didn't go through">{error.message} You haven&apos;t been charged.</Alert>;
}
