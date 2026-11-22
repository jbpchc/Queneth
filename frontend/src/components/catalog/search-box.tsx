"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { forwardRef, useEffect, useId, useMemo, useState } from "react";

import { Price } from "@/components/ui/price";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface Option {
  href: string;
  label: string;
  group: "Pieces" | "Houses" | "Boutiques" | "Categories";
  image?: string | null;
  meta?: string;
  price?: number;
}

function useDebounced<T>(value: T, ms = 150): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/**
 * Header search with autosuggest (products, houses, boutiques, categories).
 * ARIA combobox: arrow keys move, Enter opens the highlighted result or runs
 * a full search, Escape closes. UX: Jakob's Law — search lives in the header.
 */
export const SearchBox = forwardRef<
  HTMLInputElement,
  { size?: "header" | "page"; defaultValue?: string; autoFocus?: boolean; className?: string }
>(function SearchBox({ size = "header", defaultValue = "", autoFocus, className }, ref) {
  const router = useRouter();
  const listId = useId();
  const [q, setQ] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const term = useDebounced(q.trim());

  const suggest = useQuery({
    queryKey: ["suggest", term],
    enabled: term.length >= 2,
    queryFn: async () => (await api.GET("/api/v1/catalog/suggest", { params: { query: { q: term } } })).data ?? null,
    staleTime: 60_000,
  });

  const options = useMemo<Option[]>(() => {
    const s = suggest.data;
    if (!s) return [];
    return [
      ...s.products.map((p) => ({ href: `/p/${p.slug}`, label: p.title, group: "Pieces" as const, image: p.image?.url, meta: p.brand.name, price: p.price_qc })),
      ...s.brands.map((b) => ({ href: `/search?q=${encodeURIComponent(b.name)}`, label: b.name, group: "Houses" as const })),
      ...s.boutiques.map((b) => ({ href: `/b/${b.slug}`, label: b.name, group: "Boutiques" as const, image: b.logo_url, meta: b.city ?? undefined })),
      ...s.categories.map((c) => ({ href: `/c/${c.slug}`, label: c.name, group: "Categories" as const })),
    ];
  }, [suggest.data]);

  const showList = open && term.length >= 2;

  function submit(href?: string) {
    setOpen(false);
    router.push(href ?? (q.trim() ? `/search?q=${encodeURIComponent(q.trim())}` : "/search"));
  }

  return (
    <div className={cn("relative", className)}>
      <form
        role="search"
        action="/search"
        onSubmit={(e) => {
          e.preventDefault();
          submit(active >= 0 ? options[active]?.href : undefined);
        }}
      >
        <label htmlFor={`${listId}-input`} className="sr-only">
          Search Queneth
        </label>
        <Search
          aria-hidden
          className={cn("pointer-events-none absolute top-1/2 -translate-y-1/2 text-ink-muted", size === "page" ? "left-5 size-5" : "left-3.5 size-4")}
        />
        <input
          ref={ref}
          id={`${listId}-input`}
          name="q"
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls={`${listId}-list`}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${listId}-opt-${active}` : undefined}
          autoComplete="off"
          autoFocus={autoFocus}
          value={q}
          placeholder="Search pieces, houses, notes"
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setOpen(true);
              setActive((a) => Math.min(a + 1, options.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, -1));
            } else if (e.key === "Escape") {
              setOpen(false);
              setActive(-1);
            }
          }}
          className={cn(
            "w-full rounded-pill border border-border bg-surface/70 text-ink placeholder:text-ink-muted transition-[border-color] duration-[var(--dur-fast)] hover:border-border-strong focus-visible:border-accent-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-2/40",
            size === "page" ? "h-14 pl-13 pr-5 text-body" : "h-11 pl-10 pr-10 text-small",
          )}
        />
      </form>
      {showList && (
        <div
          id={`${listId}-list`}
          role="listbox"
          aria-label="Suggestions"
          className={cn(
            "absolute z-50 mt-2 max-h-[70vh] overflow-y-auto rounded-card border border-border bg-surface p-2 shadow-3",
            size === "page" ? "inset-x-0" : "right-0 w-[min(440px,90vw)]",
          )}
        >
          {suggest.isPending ? (
            <p className="px-3 py-4 text-small text-ink-muted">Searching…</p>
          ) : options.length === 0 ? (
            <p className="px-3 py-4 text-small text-ink-muted">
              No matches for “{term}”. Press Enter to search everything.
            </p>
          ) : (
            <>
              {suggest.data?.corrected && (
                <p className="px-3 pb-1 pt-2 text-caption text-ink-muted">Showing results for “{suggest.data.corrected}”</p>
              )}
              {(["Pieces", "Houses", "Boutiques", "Categories"] as const).map((group) => {
                const items = options.map((o, i) => ({ o, i })).filter(({ o }) => o.group === group);
                if (!items.length) return null;
                return (
                  <div key={group} role="group" aria-label={group}>
                    <p className="px-3 pb-1 pt-3 text-caption font-bold uppercase tracking-[0.12em] text-ink-muted">{group}</p>
                    {items.map(({ o, i }) => (
                      <div
                        key={o.href}
                        id={`${listId}-opt-${i}`}
                        role="option"
                        aria-selected={active === i}
                        onMouseDown={(e) => {
                          e.preventDefault();
                          submit(o.href);
                        }}
                        onMouseEnter={() => setActive(i)}
                        className={cn("flex min-h-12 cursor-pointer items-center gap-3 rounded-input px-3 py-1.5", active === i && "bg-surface-muted")}
                      >
                        {o.image && (
                          <span className="relative size-10 shrink-0 overflow-hidden rounded-input bg-surface-muted">
                            <Image src={o.image} alt="" fill sizes="40px" className="object-cover" />
                          </span>
                        )}
                        <span className="flex min-w-0 flex-1 flex-col">
                          <span className="truncate text-small font-semibold text-ink">{o.label}</span>
                          {o.meta && <span className="truncate text-caption text-ink-muted">{o.meta}</span>}
                        </span>
                        {o.price !== undefined && <Price amount={o.price} size="sm" />}
                      </div>
                    ))}
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
});
