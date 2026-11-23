"use client";

import { Gift, Heart, ShieldCheck, Store } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useSession } from "@/lib/auth/session";

const PERKS = [
  { icon: Gift, text: "QC 50,000 welcome credit in your QueWallet" },
  { icon: Heart, text: "Save pieces and follow your favourite boutiques" },
  { icon: ShieldCheck, text: "Escrow on every order until it arrives" },
  { icon: Store, text: "Open your own boutique from the same account" },
];

/**
 * Sign-up invitation for visitors who aren't signed in. Hidden while the
 * session loads (no flash for members) and for anyone signed in.
 * UX: Von Restorff effect — a full-width contrasting band right under the hero.
 * UX: Goal-gradient — the welcome credit is the first perk, so the reward is concrete.
 */
export function GuestWelcome() {
  const { status } = useSession();
  // Server HTML never knows the session; render only after mount so hydration matches.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted || status !== "guest") return null;
  return (
    <section aria-labelledby="guest-welcome" className="mx-auto w-full max-w-[1536px] px-4 sm:px-6 lg:px-10">
      <div className="grain relative grid gap-8 overflow-hidden rounded-card border border-border bg-surface p-8 shadow-2 md:grid-cols-12 md:items-center md:p-12">
        <div className="relative z-[1] flex flex-col gap-4 md:col-span-6">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-accent">New to Queneth?</p>
          <h2 id="guest-welcome" className="text-h1 text-ink">
            Join free and get <span className="whitespace-nowrap italic text-accent">QC 50,000</span> to shop with.
          </h2>
          <p className="max-w-measure text-ink-muted">
            One account to shop every boutique, track your orders and pay with QueWallet.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button asChild variant="primary" size="lg">
              <Link href="/register">Create your account</Link>
            </Button>
            <Button asChild variant="ghost" size="lg">
              <Link href="/login">I already have one · Sign in</Link>
            </Button>
          </div>
        </div>
        <ul className="relative z-[1] grid gap-3 sm:grid-cols-2 md:col-span-6">
          {PERKS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-start gap-3 rounded-card bg-surface-muted p-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-accent text-on-accent">
                <Icon aria-hidden className="size-5" />
              </span>
              <span className="text-small font-semibold text-ink">{text}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
