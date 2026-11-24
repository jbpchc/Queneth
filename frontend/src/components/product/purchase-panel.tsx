"use client";

import { CircleAlert, CircleCheck, CircleX, ShoppingBag, Zap } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { WishlistHeart } from "@/components/catalog/wishlist-heart";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Price } from "@/components/ui/price";
import { toApiError, type ApiSchemas } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { formatQc, optionLabel } from "@/lib/format";
import { pop } from "@/lib/motion";
import { useAddToBag, useBagLine } from "@/lib/shop";
import { cn } from "@/lib/utils";

import { useProductView } from "./product-view";

type Detail = ApiSchemas["ProductDetail"];
type Variant = ApiSchemas["VariantOut"];

const AXIS_LABEL: Record<string, string> = { color: "Color", size: "Size", width: "Width", volume: "Volume", metal: "Metal" };

function valuesFor(variants: Variant[], axis: string): string[] {
  const out: string[] = [];
  for (const v of variants) {
    const val = v.options[axis];
    if (val && !out.includes(val)) out.push(val);
  }
  return out;
}

/**
 * UX: Proximity — price, option pickers and Add to Bag form one tight group.
 * UX: Fitts's Law — the 48px CTA is full width and sticks to the bottom on mobile.
 */
export function PurchasePanel({ product, sizeHelp }: { product: Detail; sizeHelp?: ReactNode }) {
  const axes = product.variant_axes;
  const { color, setColor } = useProductView();
  const swatchHex = Object.fromEntries(product.colors.map((c) => [c.name, c.hex]));
  const [selected, setSelected] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const axis of axes) {
      const vals = valuesFor(product.variants, axis);
      // Preselect only when there's no real choice, or for color (shown in the gallery).
      if (vals.length === 1) init[axis] = vals[0]!;
      else if ((axis === "color" || axis === "metal") && color && vals.includes(color)) init[axis] = color;
      else if (axis === "color" || axis === "metal") {
        const firstInStock = product.variants.find((v) => v.stock > 0)?.options[axis];
        if (firstInStock) init[axis] = firstInStock;
      }
    }
    return init;
  });
  const [missing, setMissing] = useState<string | null>(null);
  const add = useAddToBag();
  const [buying, setBuying] = useState(false);
  const { remove } = useBagLine();
  const { status, can } = useSession();
  const router = useRouter();
  const reduce = useReducedMotion();

  const matches = (v: Variant, sel: Record<string, string>) => Object.entries(sel).every(([k, val]) => v.options[k] === val);
  const variant = useMemo(
    () => (axes.every((a) => selected[a]) ? product.variants.find((v) => matches(v, selected)) : undefined),
    [axes, selected, product.variants],
  );
  const isAvailable = (axis: string, value: string) => {
    const others = Object.fromEntries(Object.entries(selected).filter(([k]) => k !== axis));
    return product.variants.some((v) => v.options[axis] === value && matches(v, others) && v.stock > 0);
  };

  const price = variant?.price_qc ?? product.price_qc;
  const compareAt = variant ? variant.compare_at_qc : product.compare_at_qc;
  const soldOut = product.total_stock === 0;
  const shopper = status !== "authenticated" || can("cart:manage");

  function choose(axis: string, value: string) {
    setSelected((s) => ({ ...s, [axis]: value }));
    setMissing(null);
    if (axis === "color" || axis === "metal") setColor(value);
  }

  /** The chosen variant once every option is picked and the shopper is signed in. */
  function ready(signInTitle: string): Variant | null {
    const need = axes.find((a) => !selected[a]);
    if (need) {
      setMissing(need);
      document.getElementById(`axis-${need}`)?.focus();
      return null;
    }
    if (!variant) return null;
    if (status !== "authenticated") {
      toast(signInTitle, {
        description: "Your bag and orders are saved to your account.",
        action: { label: "Sign in", onClick: () => router.push(`/login?next=/p/${product.slug}`) },
      });
      return null;
    }
    return variant;
  }

  /** Buy now: put exactly this piece in the bag and check out only it. */
  async function buyNow() {
    const variant = ready("Sign in to buy");
    if (!variant) return;
    try {
      const bag = await add.mutateAsync({ variantId: variant.id, buyNow: true });
      const line = bag.groups.flatMap((g) => g.items).find((i) => i.variant_id === variant.id);
      if (!line) throw new Error("This piece couldn't be added.");
      setBuying(true);
      router.push(`/checkout?items=${line.id}`);
    } catch (err) {
      toast.error("Couldn't start checkout", { description: toApiError(err).message });
    }
  }

  async function addToBag() {
    const variant = ready("Sign in to add to your bag");
    if (!variant) return;
    try {
      const bag = await add.mutateAsync({ variantId: variant.id });
      const line = bag.groups.flatMap((g) => g.items).find((i) => i.variant_id === variant.id);
      const label = optionLabel(variant.options);
      toast.success("Added to your bag", {
        description: `${product.title} · ${label}`,
        action: { label: "View bag", onClick: () => router.push("/bag") },
        cancel: line ? { label: "Undo", onClick: () => remove.mutate(line.id) } : undefined,
      });
    } catch (err) {
      toast.error("Couldn't add to bag", { description: toApiError(err).message });
    }
  }

  const stock = variant?.stock ?? null;
  const stockState =
    soldOut || stock === 0
      ? { icon: CircleX, text: soldOut ? "Sold out" : "This option is sold out", tone: "text-danger" }
      : stock !== null && variant?.low_stock
        ? { icon: CircleAlert, text: `Only ${stock} left`, tone: "text-warning" }
        : { icon: CircleCheck, text: "In stock · ships in 2–4 days", tone: "text-success" };
  const StockIcon = stockState.icon;

  const unavailable = soldOut || stock === 0 || !shopper;
  const pending = add.isPending || buying;
  // Two ways to order: keep shopping (Add to Bag) or go straight to paying (Buy now).
  const cta = unavailable ? (
    <Button variant="primary" size="lg" block disabled>
      <ShoppingBag aria-hidden />
      {soldOut ? "Sold out" : !shopper ? "Shopping is for buyer accounts" : "This option is sold out"}
    </Button>
  ) : (
    <div className="grid grid-cols-2 gap-3">
      <Button variant="outline" size="lg" block onClick={addToBag} disabled={pending} loading={add.isPending && !add.variables?.buyNow}>
        <ShoppingBag aria-hidden />
        Add to Bag
      </Button>
      <Button variant="primary" size="lg" block onClick={buyNow} disabled={pending} loading={buying || (add.isPending && !!add.variables?.buyNow)}>
        <Zap aria-hidden />
        Buy now
      </Button>
    </div>
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-baseline justify-between gap-4">
        <Price amount={price} compareAt={compareAt} size="lg" />
        {compareAt && compareAt > price && (
          <span className="text-small font-semibold text-tangerine">
            Save {formatQc(compareAt - price)}
          </span>
        )}
      </div>

      {axes.map((axis) => {
        const vals = valuesFor(product.variants, axis);
        const isSwatch = axis === "color" || axis === "metal";
        return (
          <fieldset key={axis} className="flex flex-col gap-3">
            <legend className="mb-3 flex w-full items-baseline justify-between text-small">
              <span className="font-semibold text-ink">
                {AXIS_LABEL[axis] ?? axis}
                {selected[axis] && <span className="ml-2 font-normal text-ink-muted">{selected[axis]}</span>}
              </span>
              {axis === "size" && sizeHelp}
            </legend>
            <div id={`axis-${axis}`} tabIndex={-1} role="group" aria-label={AXIS_LABEL[axis]} className="flex flex-wrap gap-2 focus:outline-none">
              {vals.map((val) => {
                const on = selected[axis] === val;
                const avail = isAvailable(axis, val);
                if (isSwatch && swatchHex[val]) {
                  return (
                    <button
                      key={val}
                      type="button"
                      aria-pressed={on}
                      aria-label={`${val}${avail ? "" : " (sold out)"}`}
                      title={val}
                      onClick={() => choose(axis, val)}
                      className={cn(
                        "relative grid size-11 place-items-center rounded-full ring-offset-2 ring-offset-bg transition-shadow",
                        on ? "ring-2 ring-ink" : "hover:ring-2 hover:ring-border-strong",
                      )}
                    >
                      <span className="size-8 rounded-full border border-border-strong/40" style={{ background: swatchHex[val] ?? undefined }} />
                      {!avail && <span aria-hidden className="absolute h-0.5 w-9 rotate-45 bg-ink-muted" />}
                    </button>
                  );
                }
                return (
                  <motion.span key={val} animate={on && !reduce ? { scale: [1, 1.08, 1] } : { scale: 1 }} transition={pop}>
                    <Chip selected={on} onClick={() => choose(axis, val)} disabled={!avail} aria-label={`${val}${avail ? "" : " (sold out)"}`}>
                      {val}
                    </Chip>
                  </motion.span>
                );
              })}
            </div>
            {missing === axis && (
              <p role="alert" className="flex items-center gap-1.5 text-small text-danger">
                <CircleAlert aria-hidden className="size-4" /> Choose a {AXIS_LABEL[axis]?.toLowerCase() ?? axis} first.
              </p>
            )}
          </fieldset>
        );
      })}

      <p className={cn("flex items-center gap-2 text-small font-semibold", stockState.tone)} aria-live="polite">
        <StockIcon aria-hidden className="size-4" /> {stockState.text}
      </p>

      <div className="hidden items-center gap-3 md:flex">
        <div className="flex-1">{cta}</div>
        <WishlistHeart productId={product.id} title={product.title} size="lg" className="border border-border" />
      </div>

      {/* Mobile: sticky purchase bar above the tab bar. */}
      <div className="fixed inset-x-0 bottom-16 z-30 flex items-center gap-3 border-t border-border bg-[var(--glass)] px-4 py-3 backdrop-blur-xl md:hidden">
        <div className="flex-1">{cta}</div>
        <WishlistHeart productId={product.id} title={product.title} size="lg" className="border border-border" />
      </div>

      {!shopper && (
        <p className="text-small text-ink-muted">
          Admin accounts can&apos;t shop. <Link href="/admin" className="font-semibold text-accent-2 underline">Go to the Control Room</Link>
        </p>
      )}
    </div>
  );
}
