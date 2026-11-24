import Link from "next/link";

import { Logo } from "./logo";

const columns = [
  {
    title: "Shop",
    links: [
      { label: "New arrivals", href: "/search?sort=newest" },
      { label: "Queneth Drops", href: "/drops" },
      { label: "Boutiques", href: "/boutiques" },
      { label: "Perfumes", href: "/c/perfumes" },
    ],
  },
  {
    title: "Your account",
    links: [
      { label: "Orders", href: "/account/orders" },
      { label: "QueWallet", href: "/account/wallet" },
      { label: "Open a boutique", href: "/register?type=seller" },
    ],
  },
  {
    title: "Studio",
    links: [
      { label: "Style guide", href: "/styleguide" },
      { label: "Seller Studio", href: "/seller" },
    ],
  },
];

export function SiteFooter() {
  return (
    // Bottom padding clears the mobile tab bar.
    <footer className="mt-24 border-t border-border bg-surface-muted pb-24 md:pb-0">
      <div className="mx-auto grid max-w-[1536px] gap-12 px-4 py-16 sm:px-6 md:grid-cols-[1.5fr_repeat(3,1fr)] lg:px-10">
        <div className="flex max-w-sm flex-col gap-4">
          <Logo />
          <p className="font-display text-h3 italic text-ink">Curated for the connoisseur.</p>
          <p className="text-small text-ink-muted">
            Independent boutiques, authenticated pieces, and the notes behind every scent.
          </p>
        </div>
        {columns.map((col) => (
          <nav key={col.title} aria-label={col.title}>
            <h2 className="mb-4 font-sans text-caption font-bold uppercase tracking-[0.12em] text-ink-muted">
              {col.title}
            </h2>
            <ul className="flex flex-col gap-1">
              {col.links.map((l) => (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    prefetch={false} // footer links aren't worth preloading on every page
                    className="inline-flex min-h-11 items-center text-small text-ink hover:text-accent-2 hover:underline hover:underline-offset-4"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="border-t border-border">
        <div className="mx-auto flex max-w-[1536px] flex-col gap-2 px-4 py-6 text-caption text-ink-muted sm:px-6 md:flex-row md:justify-between lg:px-10">
          <p>
            <strong className="font-semibold text-ink">
              QueWallet credits are simulated for academic purposes and have no cash value.
            </strong>{" "}
            Queneth is an academic capstone; all brands and boutiques are fictional.
          </p>
          <p>© {new Date().getFullYear()} Queneth</p>
        </div>
      </div>
    </footer>
  );
}
