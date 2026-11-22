"use client";

import { Heart, PackageOpen, Plus, Wallet } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { AddressPicker, emptyPlace, type AddressPlace } from "@/components/forms/address-picker";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox, Switch } from "@/components/ui/checkbox";
import { Chip } from "@/components/ui/chip";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Price } from "@/components/ui/price";
import { Progress, ProgressRing } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { ProductCardSkeleton, Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Alert, EmptyState, ErrorState } from "@/components/ui/states";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Tooltip } from "@/components/ui/tooltip";
import { chunkReference, formatQc } from "@/lib/format";
import { pop, spring } from "@/lib/motion";
import { useBagUi } from "@/lib/stores/bag-ui";

function Section({ id, title, intro, children }: { id: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-28 border-t border-border pt-10">
      <h2 id={`${id}-title`} className="text-h2 text-ink">
        {title}
      </h2>
      {intro && <p className="mt-2 max-w-measure text-ink-muted">{intro}</p>}
      <div className="mt-8">{children}</div>
    </section>
  );
}

function Specimen({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={className}>
      <p className="mb-3 text-caption font-bold uppercase tracking-[0.12em] text-ink-muted">{label}</p>
      {children}
    </div>
  );
}

const swatches = [
  { group: "Surfaces & ink", items: [["--bg", "Page background"], ["--surface", "Cards, sheets"], ["--surface-muted", "Bands, inputs"], ["--border", "Hairlines"], ["--border-strong", "Control outlines"], ["--ink", "Primary text"], ["--ink-muted", "Secondary text"]] },
  { group: "Brand", items: [["--accent", "Que Magenta · primary CTA"], ["--accent-2", "Electric Cobalt · links, wallet"]] },
  { group: "Pops (ink text only)", items: [["--pop-citrus", "New drop"], ["--pop-tangerine", "Sale, rewards"], ["--pop-lilac", "Tiers"]] },
  { group: "Status", items: [["--success", "Success"], ["--warning", "Warning"], ["--danger", "Danger"]] },
] as const;

const typeScale = [
  ["Display", "text-display", "Fraunces · 56→96px", "Quiet luxury"],
  ["H1", "text-h1", "Fraunces · 40→56px", "The Citrus & Sun edit"],
  ["H2", "text-h2", "Fraunces · 28→36px", "New from boutiques you follow"],
  ["H3", "text-h3", "Fraunces · 20→24px", "Materials and care"],
  ["Body", "text-body font-sans", "Manrope · 16px / 1.6", "A bias-cut slip in sand-washed silk with a liquid drape."],
  ["Small", "text-small font-sans", "Manrope · 14px", "Ships from Atelier Lumen in 2–3 days."],
  ["Caption", "text-caption font-sans", "Manrope · 12px", "Model is 175cm and wears size S."],
] as const;

export function StyleguideContent() {
  const reduce = useReducedMotion();
  const bump = useBagUi((s) => s.bump);
  const setCount = useBagUi((s) => s.setCount);
  const [size, setSize] = useState("M");
  const [hearted, setHearted] = useState(false);
  const [voucher, setVoucher] = useState("");
  const [loading, setLoading] = useState(false);
  const [place, setPlace] = useState<AddressPlace>(emptyPlace);
  const voucherError = voucher && !/^[A-Z0-9-]{4,}$/.test(voucher.replace(/\s/g, "").toUpperCase())
    ? "Voucher codes use letters, numbers and dashes."
    : undefined;

  return (
    <div className="flex min-w-0 flex-col gap-16">
      <Section id="colors" title="Color" intro="Calm porcelain and ink with saturated pops reserved for action. Every text pair passes WCAG AA; status shades were darkened from the brief to pass.">
        <div className="flex flex-col gap-8">
          {swatches.map((g) => (
            <Specimen key={g.group} label={g.group}>
              <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
                {g.items.map(([token, use]) => (
                  <li key={token} className="overflow-hidden rounded-card border border-border bg-surface">
                    <div className="h-16 border-b border-border" style={{ background: `var(${token})` }} />
                    <div className="p-3">
                      <code className="text-small font-semibold text-ink">{token}</code>
                      <p className="text-caption text-ink-muted">{use}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </Specimen>
          ))}
        </div>
      </Section>

      <Section id="type" title="Typography" intro="Fraunces (variable serif with optical sizing) for display; Manrope for UI and body. Fluid sizes with clamp(); text width capped at 68ch.">
        <ul className="flex flex-col divide-y divide-border">
          {typeScale.map(([name, cls, meta, sample]) => (
            <li key={name} className="grid gap-2 py-5 md:grid-cols-[160px_1fr] md:items-baseline">
              <div>
                <p className="text-small font-semibold text-ink">{name}</p>
                <p className="text-caption text-ink-muted">{meta}</p>
              </div>
              <p className={`${cls} text-ink`}>{sample}</p>
            </li>
          ))}
        </ul>
        <p className="mt-6 text-small text-ink-muted">
          Prices use tabular numerals: <span className="tabular font-bold text-ink">QC 1,111 · QC 8,888</span>. References are chunked (Miller&apos;s Law):{" "}
          <code className="font-semibold text-ink">{chunkReference("QN202648210 7")}</code>
        </p>
      </Section>

      <Section id="space" title="Space & shape" intro="4px base grid. Radius 8 for inputs, 20 for cards, pill for buttons and chips. Three soft, warm-tinted elevations.">
        <div className="grid gap-10 lg:grid-cols-2">
          <Specimen label="Spacing scale">
            <ul className="flex flex-col gap-2">
              {[4, 8, 12, 16, 24, 32, 48, 64, 96].map((n) => (
                <li key={n} className="flex items-center gap-3">
                  <span className="tabular w-10 text-right text-caption text-ink-muted">{n}</span>
                  <span className="h-3 rounded-pill bg-lilac" style={{ width: n * 2 }} />
                </li>
              ))}
            </ul>
          </Specimen>
          <Specimen label="Radius & elevation">
            <div className="grid grid-cols-3 gap-4">
              {(["shadow-1", "shadow-2", "shadow-3"] as const).map((s, i) => (
                <div key={s} className={`grid h-24 place-items-center rounded-card bg-surface text-caption text-ink-muted ${s}`}>
                  Level {i + 1}
                </div>
              ))}
              <div className="grid h-12 place-items-center rounded-input border border-border-strong text-caption text-ink-muted">8px</div>
              <div className="grid h-12 place-items-center rounded-card border border-border-strong text-caption text-ink-muted">20px</div>
              <div className="grid h-12 place-items-center rounded-pill border border-border-strong text-caption text-ink-muted">pill</div>
            </div>
          </Specimen>
        </div>
      </Section>

      <Section id="motion" title="Motion" intro="instant 100ms · fast 180ms · base 280ms · celebrate 600–1200ms. Spring: stiffness 400, damping 28. With reduced motion, movement becomes a fade.">
        <div className="flex flex-wrap items-center gap-6">
          <motion.button
            type="button"
            aria-pressed={hearted}
            aria-label={hearted ? "Remove from wishlist" : "Save to wishlist"}
            onClick={() => setHearted((h) => !h)}
            whileTap={reduce ? undefined : { scale: 0.9 }}
            animate={hearted && !reduce ? { scale: [1, 1.3, 1] } : { scale: 1 }}
            transition={pop}
            className="grid size-12 place-items-center rounded-full border border-border bg-surface shadow-1"
          >
            <Heart aria-hidden className={hearted ? "size-5 fill-accent text-accent" : "size-5 text-ink"} />
          </motion.button>
          <Button onClick={() => bump()} variant="outline">
            <Plus aria-hidden /> Bump bag badge
          </Button>
          <Button onClick={() => setCount(0)} variant="ghost">
            Reset badge
          </Button>
          <p className="text-small text-ink-muted">The heart springs 1 → 1.3 → 1; the header badge bounces.</p>
        </div>
      </Section>

      <Section id="buttons" title="Buttons" intro="One button system. Exactly one magenta primary per view (Von Restorff). Primary CTAs are 48px tall (Fitts's Law); every target is at least 44px.">
        <div className="flex flex-col gap-8">
          <Specimen label="Variants">
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="primary">Add to Bag</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="outline">Outline</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="wallet" className="shimmer">
                <Wallet aria-hidden /> Pay with QueWallet
              </Button>
              <Button variant="danger">Cancel order</Button>
              <Button variant="link">View size guide</Button>
            </div>
          </Specimen>
          <Specimen label="Sizes & states">
            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm">Small</Button>
              <Button size="md">Medium</Button>
              <Button size="lg">Large</Button>
              <Button size="icon" variant="outline" aria-label="Add">
                <Plus aria-hidden />
              </Button>
              <Button
                loading={loading}
                onClick={() => {
                  setLoading(true);
                  setTimeout(() => setLoading(false), 1500);
                }}
              >
                {loading ? "Saving" : "Click to load"}
              </Button>
              <Button disabled>Disabled</Button>
            </div>
          </Specimen>
          <Specimen label="Full-width mobile CTA">
            <div className="max-w-sm">
              <Button variant="primary" size="lg" block>
                Add to Bag · {formatQc(18500)}
              </Button>
            </div>
          </Specimen>
        </div>
      </Section>

      <Section id="forms" title="Forms" intro="Labelled fields with helper text and inline validation announced through aria-live. Inputs are 48px tall.">
        <div className="grid max-w-3xl gap-6 md:grid-cols-2">
          <Field label="Full name" hint="As it should appear on the parcel.">
            <Input placeholder="Isabela Reyes" autoComplete="name" />
          </Field>
          <Field label="Mobile number" hint="Any format works: 0917 123 4567 or +63 917…">
            <Input type="tel" placeholder="0917 123 4567" autoComplete="tel" />
          </Field>
          <Field label="Voucher code" hint="Spaces are fine; we'll tidy it up." error={voucherError}>
            <Input value={voucher} onChange={(e) => setVoucher(e.target.value)} placeholder="QUE-DEMO-5000" />
          </Field>
          <Field label="Size">
            <Select defaultValue="">
              <option value="" disabled>
                Choose a size
              </option>
              <option>XS</option>
              <option>S</option>
              <option>M</option>
            </Select>
          </Field>
          <Field label="Delivery note" optional className="md:col-span-2">
            <Textarea placeholder="Leave with the concierge." />
          </Field>
          <div className="flex flex-col gap-3 md:col-span-2">
            <p className="text-caption font-bold uppercase tracking-[0.12em] text-ink-muted">
              PSGC address picker (live API · cache · offline snapshot)
            </p>
            <AddressPicker value={place} onChange={setPlace} />
            <p aria-live="polite" className="text-small text-ink-muted">
              {place.barangay
                ? `${place.barangay.name}, ${place.city?.name}${place.province ? `, ${place.province.name}` : ""}, ${place.region?.name}`
                : "Pick down to the barangay."}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Checkbox id="sg-default" defaultChecked />
            <Label htmlFor="sg-default">Set as default address</Label>
          </div>
          <div className="flex items-center gap-3">
            <Switch id="sg-notify" />
            <Label htmlFor="sg-notify">Notify me when this drop goes live</Label>
          </div>
        </div>
      </Section>

      <Section id="chips" title="Chips & badges" intro="One chip style for sizes, filters and sort. Pops always carry ink text and appear only when true.">
        <div className="flex flex-col gap-8">
          <Specimen label="Size selector">
            <div role="group" aria-label="Size" className="flex flex-wrap gap-2">
              {["XS", "S", "M", "L", "XL"].map((s) => (
                <Chip key={s} selected={size === s} onClick={() => setSize(s)}>
                  {s}
                </Chip>
              ))}
              <Chip disabled>XXL</Chip>
            </div>
          </Specimen>
          <Specimen label="Badges">
            <div className="flex flex-wrap gap-2">
              <Badge tone="citrus">New drop</Badge>
              <Badge tone="citrus">Last 2 left</Badge>
              <Badge tone="tangerine">−20%</Badge>
              <Badge tone="lilac">Connoisseur</Badge>
              <Badge tone="ink">Connoisseur&apos;s pick</Badge>
              <Badge>Pre-loved Excellent</Badge>
              <Badge tone="success">Delivered</Badge>
              <Badge tone="warning">Processing</Badge>
              <Badge tone="danger">Cancelled</Badge>
              <Badge tone="info">Shipped</Badge>
            </div>
          </Specimen>
        </div>
      </Section>

      <Section id="commerce" title="Price & cards" intro="Product cards show image, brand, name, price and the heart — nothing else until hover (Prägnanz). Skeletons match the final layout.">
        <div className="grid gap-10">
          <Specimen label="Price">
            <div className="flex flex-wrap items-end gap-8">
              <Price amount={18500} size="lg" />
              <Price amount={14800} compareAt={18500} />
              <Price amount={2450} size="sm" />
            </div>
          </Specimen>
          <div className="grid grid-cols-2 gap-x-4 gap-y-10 md:grid-cols-4">
            {[
              { brand: "Maison Verdé", name: "Bias-cut silk slip dress", price: 18500, hue: "from-lilac/60 to-surface-muted" },
              { brand: "Nocturne Parfums", name: "Figue Noire Eau de Parfum", price: 9200, hue: "from-tangerine/40 to-surface-muted" },
            ].map((p) => (
              <article key={p.name} className="group flex flex-col gap-3">
                <div className={`relative aspect-[4/5] overflow-hidden rounded-card bg-gradient-to-br ${p.hue} transition-shadow duration-[var(--dur-fast)] group-hover:shadow-2`}>
                  <button type="button" aria-label={`Save ${p.name}`} className="absolute right-2 top-2 grid size-11 place-items-center rounded-full bg-surface/80 backdrop-blur">
                    <Heart aria-hidden className="size-5 text-ink" />
                  </button>
                </div>
                <div className="flex flex-col gap-0.5">
                  <p className="text-caption font-bold uppercase tracking-[0.1em] text-ink-muted">{p.brand}</p>
                  <h3 className="font-sans text-small font-semibold text-ink">{p.name}</h3>
                  <Price amount={p.price} size="sm" />
                </div>
              </article>
            ))}
            <ProductCardSkeleton />
            <ProductCardSkeleton />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Order {chunkReference("QN2026482107")}</CardTitle>
                <CardDescription>Atelier Lumen · 2 items</CardDescription>
              </CardHeader>
              <CardContent className="flex items-center justify-between">
                <Badge tone="info">Shipped</Badge>
                <Price amount={27700} />
              </CardContent>
              <CardFooter>
                <Button variant="outline" size="sm">Track parcel</Button>
              </CardFooter>
            </Card>
            <Card interactive>
              <CardContent className="flex items-center gap-4">
                <Avatar name="Atelier Lumen" size={56} />
                <div className="flex-1">
                  <p className="font-semibold text-ink">Atelier Lumen</p>
                  <p className="text-small text-ink-muted">Independent boutique · 1.2k followers</p>
                </div>
                <Button variant="outline" size="sm">Follow</Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </Section>

      <Section id="progress" title="Progress" intro="Goal-Gradient effect: show how close people are to finishing.">
        <div className="grid items-center gap-10 md:grid-cols-[1fr_auto]">
          <div className="flex max-w-md flex-col gap-6">
            <Progress label="Your style profile" value={80} />
            <Progress label="Checkout · Step 2 of 3" value={66} tone="accent" />
            <Progress label="Seller onboarding" value={33} tone="wallet" />
          </div>
          <ProgressRing value={62} label="Progress to Connoisseur tier">
            <span className="flex flex-col">
              <span className="tabular font-display text-h3 text-ink">62%</span>
              <span className="text-caption text-ink-muted">to Connoisseur</span>
            </span>
          </ProgressRing>
        </div>
      </Section>

      <Section id="disclosure" title="Tabs & accordion" intro="Product details are chunked into tabs on desktop and accordions on mobile.">
        <div className="grid gap-10 lg:grid-cols-2">
          <Tabs defaultValue="notes">
            <TabsList aria-label="Product details">
              <TabsTrigger value="details">Details</TabsTrigger>
              <TabsTrigger value="notes">Notes</TabsTrigger>
              <TabsTrigger value="shipping">Shipping</TabsTrigger>
            </TabsList>
            <TabsContent value="details">Eau de Parfum, 50ml. Composed by Léa Marchetti.</TabsContent>
            <TabsContent value="notes">Top: bergamot, pink pepper. Heart: fig leaf, iris. Base: cedar, ambrette.</TabsContent>
            <TabsContent value="shipping">Ships in 2–3 days from Cebu. Simulated tracking.</TabsContent>
          </Tabs>
          <Accordion type="single" collapsible defaultValue="care">
            <AccordionItem value="materials">
              <AccordionTrigger>Materials</AccordionTrigger>
              <AccordionContent>100% mulberry silk, 19 momme. Lined in cupro.</AccordionContent>
            </AccordionItem>
            <AccordionItem value="care">
              <AccordionTrigger>Care</AccordionTrigger>
              <AccordionContent>Dry clean only. Steam on low; never wring.</AccordionContent>
            </AccordionItem>
            <AccordionItem value="fit">
              <AccordionTrigger>Size and fit</AccordionTrigger>
              <AccordionContent>Runs true to size. Model is 175cm and wears S.</AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </Section>

      <Section id="overlays" title="Overlays & toasts" intro="Focus is trapped in dialogs and sheets and returns to the trigger on close. Mobile filters use a bottom sheet.">
        <div className="flex flex-wrap gap-3">
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline">Open dialog</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Size guide</DialogTitle>
                <DialogDescription>Measurements in centimetres, taken flat.</DialogDescription>
              </DialogHeader>
              <p className="mt-4 text-small text-ink-muted">Bust 84 · Waist 66 · Hip 92 for size S.</p>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="secondary">Got it</Button>
                </DialogClose>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline">Bottom sheet</Button>
            </SheetTrigger>
            <SheetContent side="bottom" aria-describedby={undefined}>
              <DialogTitle>Filters</DialogTitle>
              <div className="flex flex-wrap gap-2">
                {["Silk", "Wool", "Cashmere", "Linen"].map((m) => (
                  <Chip key={m}>{m}</Chip>
                ))}
              </div>
              <Button variant="secondary" size="lg" block>
                Show 48 pieces
              </Button>
            </SheetContent>
          </Sheet>
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline">Side drawer</Button>
            </SheetTrigger>
            <SheetContent side="right" aria-describedby={undefined}>
              <DialogTitle>Transaction QN-TX-8841-02</DialogTitle>
              <p className="text-small text-ink-muted">Ledger entries appear here in Phase 5.</p>
            </SheetContent>
          </Sheet>
          <Tooltip content="Sillage: how far a scent projects from the skin.">
            <Button variant="ghost">Hover for tooltip</Button>
          </Tooltip>
          <Button
            variant="outline"
            onClick={() =>
              toast("Added to your bag", {
                description: "Bias-cut silk slip dress · S",
                action: { label: "View bag", onClick: () => undefined },
                cancel: { label: "Undo", onClick: () => undefined },
              })
            }
          >
            Show toast
          </Button>
        </div>
      </Section>

      <Section id="states" title="States" intro="Every page ships loading, empty, error and success states. Empty states always offer the next action.">
        <div className="grid gap-6 lg:grid-cols-2">
          <EmptyState
            icon={PackageOpen}
            title="Your wishlist is waiting"
            description="Tap the heart on anything that catches your eye. Isabela keeps a board for every season."
            action={<Button variant="secondary">Browse new arrivals</Button>}
          />
          <ErrorState message="We couldn't load your orders. Your wallet and bag are safe." onRetry={() => toast("Retrying…")} />
          <div className="flex flex-col gap-3 lg:col-span-2">
            <Alert tone="info" title="Simulated top-up">
              QueWallet credits are simulated for academic purposes and have no cash value.
            </Alert>
            <Alert tone="success" title="Order placed">You earned 185 Que Points.</Alert>
            <Alert tone="warning" title="Low stock">Only 2 left in size M.</Alert>
            <Alert tone="danger" title="Not enough QC">Top up or redeem a code to continue.</Alert>
          </div>
          <div className="flex items-center gap-4">
            <Spinner /> <span className="text-small text-ink-muted">Inline loading</span>
          </div>
          <div className="flex flex-col gap-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </div>
      </Section>
    </div>
  );
}
