import type { Metadata } from "next";
import Link from "next/link";

import { AddressBook } from "@/components/account/address-book";

export const metadata: Metadata = { title: "Addresses", robots: { index: false } };

export default function AddressesPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 pb-16 pt-8 sm:px-6 md:pt-12">
      <nav aria-label="Breadcrumb" className="mb-4 text-small text-ink-muted">
        <Link href="/account" className="hover:underline">Account</Link> / Addresses
      </nav>
      <header className="mb-8 flex flex-col gap-2">
        <h1 className="text-h1 text-ink">Addresses</h1>
        <p className="text-body text-ink-muted">Where your pieces are delivered. Your default is pre-selected at checkout.</p>
      </header>
      <AddressBook />
    </div>
  );
}
