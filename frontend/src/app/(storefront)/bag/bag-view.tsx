"use client";

import { Bookmark, Minus, Plus, ShoppingBag, Store, Tag, Trash2, Wallet, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Price } from "@/components/ui/price";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError, type ApiSchemas } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { useSaveForLater, useVouchers } from "@/lib/commerce";
import { formatQc, optionLabel } from "@/lib/format";
import { useBag, useBagLine } from "@/lib/shop";
import { useWallet } from "@/lib/wallet";

type BagItem = ApiSchemas["BagItem"];
type BagGroup = ApiSchemas["BagGroup"];

/**
 * The bag, grouped by boutique: each ships separately and is paid into escrow
 * separately, so each has its own voucher slot and subtotal.
 */
export function BagView() {
  const { status } = useSession();
  const bag = useBag();
  const wallet = useWallet();

  const header = (
    <header className="mb-8 flex flex-col gap-2">
      <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Your selection</p>
      <h1 className="text-h1 text-ink">Bag</h1>
    </header>
  );

  if (status === "guest") {
    return (
      <>
        {header}
        <EmptyState
          icon={ShoppingBag}
          title="Sign in to see your bag"
          description="Your bag is saved to your account, so it's waiting on every device."
          action={<Button asChild variant="primary"><Link href="/login?next=/bag">Sign in</Link></Button>}
        />
      </>
    );
  }
  if (status === "loading" || bag.isPending) {
    return (
      <>
        {header}
        <div className="grid gap-8 lg:grid-cols-[1fr_360px]" aria-busy="true" aria-label="Loading bag">
          <Skeleton className="h-72 rounded-card" />
          <Skeleton className="h-56 rounded-card" />
        </div>
      </>
    );
  }
  if (bag.isError) {
    return (<>{header}<ErrorState message={toApiError(bag.error).message} onRetry={() => bag.refetch()} /></>);
  }

  const data = bag.data;
  const unavailable = data.groups.some((g) => g.items.some((i) => !i.available));
  const short = wallet.data ? data.total_qc - wallet.data.balance_qc : 0;

  return (
    <>
      {header}
      {data.groups.length === 0 ? (
        <EmptyState
          icon={ShoppingBag}
          title="Your bag is empty"
          description={
            data.saved.length
              ? "Your saved pieces are below. Move one back when you're ready."
              : "Find something worth keeping. New pieces arrive from our boutiques every week."
          }
          action={<Button asChild variant="secondary"><Link href="/search?sort=newest">Browse new arrivals</Link></Button>}
        />
      ) : (
        <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
          <div className="flex min-w-0 flex-col gap-6">
            {data.groups.map((g) => <BoutiqueGroup key={g.boutique.slug} group={g} />)}
          </div>

          <aside className="flex flex-col gap-4 lg:sticky lg:top-24 lg:self-start">
            <Card className="flex flex-col gap-4 p-6">
              <h2 className="text-h3 text-ink">Summary</h2>
              <dl className="flex flex-col gap-2 text-small">
                <div className="flex justify-between"><dt className="text-ink-muted">{data.item_count} {data.item_count === 1 ? "piece" : "pieces"}</dt><dd className="tabular">{formatQc(data.subtotal_qc)}</dd></div>
                {data.discount_qc > 0 && (
                  <div className="flex justify-between text-success"><dt>Boutique vouchers</dt><dd className="tabular">−{formatQc(data.discount_qc)}</dd></div>
                )}
                <div className="flex justify-between"><dt className="text-ink-muted">Shipping</dt><dd>Included</dd></div>
                <div className="flex justify-between border-t border-border pt-3 text-body font-bold"><dt>Total</dt><dd className="tabular">{formatQc(data.total_qc)}</dd></div>
                {wallet.data && (
                  <div className="flex justify-between text-ink-muted">
                    <dt>Your QueWallet</dt>
                    <dd className={short > 0 ? "tabular font-semibold text-danger" : "tabular"}>{formatQc(wallet.data.balance_qc)}</dd>
                  </div>
                )}
              </dl>
              {short > 0 && (
                <p className="text-small text-danger">
                  {formatQc(short)} short. You can top up during checkout.
                </p>
              )}
              {unavailable ? (
                <p className="text-small font-semibold text-danger">Remove sold-out pieces to continue.</p>
              ) : null}
              {/* UX: Von Restorff — the one primary action on the page, in the wallet color. */}
              <Button asChild={!unavailable} variant="wallet" size="lg" block disabled={unavailable}>
                {unavailable ? (
                  <span><Wallet aria-hidden /> Checkout with QueWallet</span>
                ) : (
                  <Link href="/checkout"><Wallet aria-hidden /> Checkout with QueWallet</Link>
                )}
              </Button>
            </Card>
            <Alert tone="info">QueWallet credits are simulated for academic purposes and have no cash value.</Alert>
          </aside>
        </div>
      )}

      {data.saved.length > 0 && <SavedForLater items={data.saved} />}
    </>
  );
}

function BoutiqueGroup({ group: g }: { group: BagGroup }) {
  return (
    // UX: Common Region — one bounded card per boutique.
    <Card className="overflow-clip">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-5 py-4">
        <Store aria-hidden className="size-4 text-ink-muted" />
        <Link href={`/b/${g.boutique.slug}`} className="font-semibold text-ink hover:underline">{g.boutique.name}</Link>
        {g.boutique.city && <span className="text-caption text-ink-muted">· ships from {g.boutique.city}</span>}
        <span className="ml-auto tabular text-small text-ink">{formatQc(g.total_qc)}</span>
      </div>
      <ul className="divide-y divide-border">
        {g.items.map((item) => <Line key={item.id} item={item} />)}
      </ul>
      <VoucherSlot group={g} />
    </Card>
  );
}

function Line({ item }: { item: BagItem }) {
  const { setQty, remove } = useBagLine();
  const later = useSaveForLater();
  return (
    <li className="flex gap-4 p-5">
      <Link href={`/p/${item.product.slug}`} className="relative aspect-[4/5] w-24 shrink-0 overflow-hidden rounded-input bg-surface-muted">
        {item.product.image && <Image src={item.product.image.url} alt={item.product.image.alt} fill sizes="96px" className="object-cover" />}
      </Link>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="text-caption font-bold uppercase tracking-[0.1em] text-ink-muted">{item.product.brand.name}</p>
        <Link href={`/p/${item.product.slug}`} className="font-semibold text-ink hover:underline">{item.product.title}</Link>
        <p className="text-small text-ink-muted">{optionLabel(item.options)}</p>
        {!item.available && <p className="text-small font-semibold text-danger">No longer available — remove it to continue.</p>}
        {item.available && item.stock <= 3 && <p className="text-small text-warning">Only {item.stock} left</p>}
        <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-2">
          {/* Stepper with 44px targets (Fitts's Law). */}
          <div className="inline-flex items-center rounded-pill border border-border-strong" role="group" aria-label={`Quantity for ${item.product.title}`}>
            <button type="button" aria-label="Decrease quantity" disabled={item.qty <= 1 || setQty.isPending} onClick={() => setQty.mutate({ id: item.id, qty: item.qty - 1 })} className="grid size-11 place-items-center rounded-l-pill disabled:opacity-40">
              <Minus aria-hidden className="size-4" />
            </button>
            <span className="tabular w-8 text-center font-semibold" aria-live="polite">{item.qty}</span>
            <button type="button" aria-label="Increase quantity" disabled={item.qty >= Math.min(10, item.stock) || setQty.isPending} onClick={() => setQty.mutate({ id: item.id, qty: item.qty + 1 })} className="grid size-11 place-items-center rounded-r-pill disabled:opacity-40">
              <Plus aria-hidden className="size-4" />
            </button>
          </div>
          <Price amount={item.line_total_qc} />
        </div>
        <button
          type="button"
          onClick={() => later.mutate({ id: item.id, saved: true }, { onSuccess: () => toast.success("Saved for later") })}
          disabled={later.isPending}
          className="mt-1 inline-flex min-h-11 items-center gap-1.5 self-start text-small font-semibold text-accent-2 hover:underline"
        >
          <Bookmark aria-hidden className="size-4" /> Save for later
        </button>
      </div>
      {/* Destructive action kept apart from the stepper (Fitts's Law). */}
      <button type="button" onClick={() => remove.mutate(item.id)} aria-label={`Remove ${item.product.title}`} className="grid size-11 shrink-0 place-items-center self-start rounded-full text-ink-muted hover:bg-surface-muted hover:text-danger">
        <Trash2 aria-hidden className="size-4" />
      </button>
    </li>
  );
}

/**
 * One voucher per boutique. UX: Goal-Gradient — below the minimum spend the
 * voucher stays applied and says exactly how much more to add.
 */
function VoucherSlot({ group: g }: { group: BagGroup }) {
  const { apply, remove } = useVouchers();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    setError(null);
    try {
      await apply.mutateAsync(code);
      setCode("");
      setOpen(false);
      toast.success("Voucher applied");
    } catch (err) {
      setError(toApiError(err).message);
    }
  };

  if (g.voucher) {
    const v = g.voucher;
    return (
      <div className="flex flex-wrap items-center gap-3 border-t border-border bg-surface-muted/60 px-5 py-3 text-small">
        <Tag aria-hidden className={v.problem ? "size-4 text-warning" : "size-4 text-success"} />
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="font-semibold text-ink">{v.code}{v.discount_qc > 0 && <span className="ml-2 tabular text-success">−{formatQc(v.discount_qc)}</span>}</span>
          <span className={v.problem ? "text-warning" : "text-ink-muted"}>{v.problem ?? v.description}</span>
        </div>
        <button type="button" onClick={() => remove.mutate(v.id)} aria-label={`Remove voucher ${v.code}`} className="grid size-11 place-items-center rounded-full text-ink-muted hover:bg-surface hover:text-danger">
          <X aria-hidden className="size-4" />
        </button>
      </div>
    );
  }

  if (!open) {
    return (
      <div className="border-t border-border px-5 py-2">
        <button type="button" onClick={() => setOpen(true)} className="inline-flex min-h-11 items-center gap-1.5 text-small font-semibold text-accent-2 hover:underline">
          <Tag aria-hidden className="size-4" /> Add a voucher for {g.boutique.name}
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2 border-t border-border px-5 py-4" noValidate>
      <label htmlFor={`voucher-${g.boutique.slug}`} className="text-small font-semibold text-ink">Voucher code</label>
      <div className="flex gap-2">
        <Input
          id={`voucher-${g.boutique.slug}`}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="e.g. LUMEN10"
          autoCapitalize="characters"
          autoComplete="off"
          autoFocus
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `voucher-${g.boutique.slug}-error` : undefined}
          className="uppercase"
        />
        <Button type="submit" variant="secondary" loading={apply.isPending}>Apply</Button>
      </div>
      {error && <p id={`voucher-${g.boutique.slug}-error`} role="alert" className="text-small text-danger">{error}</p>}
    </form>
  );
}

function SavedForLater({ items }: { items: BagItem[] }) {
  const later = useSaveForLater();
  const { remove } = useBagLine();
  return (
    <section className="mt-12 flex flex-col gap-4" aria-labelledby="saved-heading">
      <h2 id="saved-heading" className="text-h3 text-ink">Saved for later <span className="text-ink-muted">({items.length})</span></h2>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <li key={item.id}>
            <Card className="flex gap-4 p-4">
              <Link href={`/p/${item.product.slug}`} className="relative aspect-[4/5] w-20 shrink-0 overflow-hidden rounded-input bg-surface-muted">
                {item.product.image && <Image src={item.product.image.url} alt={item.product.image.alt} fill sizes="80px" className="object-cover" />}
              </Link>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <Link href={`/p/${item.product.slug}`} className="line-clamp-2 text-small font-semibold text-ink hover:underline">{item.product.title}</Link>
                <p className="text-caption text-ink-muted">{optionLabel(item.options)}</p>
                <Price amount={item.unit_price_qc} size="sm" />
                <div className="mt-auto flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!item.available || later.isPending}
                    onClick={() => later.mutate({ id: item.id, saved: false }, { onSuccess: () => toast.success("Moved to bag") })}
                  >
                    {item.available ? "Move to bag" : "Sold out"}
                  </Button>
                  <button type="button" onClick={() => remove.mutate(item.id)} aria-label={`Remove ${item.product.title}`} className="ml-auto grid size-11 place-items-center rounded-full text-ink-muted hover:bg-surface-muted hover:text-danger">
                    <Trash2 aria-hidden className="size-4" />
                  </button>
                </div>
              </div>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
}
