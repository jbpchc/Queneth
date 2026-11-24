"use client";

import { Archive, ArchiveRestore, Copy, PackageOpen, Pencil, Plus, Search, Trash2 } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { formatNumber, formatQc } from "@/lib/format";
import { useProductActions, useStudioProducts } from "@/lib/studio";
import { cn } from "@/lib/utils";

type Tab = "draft" | "active" | "archived" | null;
const TABS: { value: Tab; label: string }[] = [
  { value: null, label: "All" },
  { value: "active", label: "Live" },
  { value: "draft", label: "Drafts" },
  { value: "archived", label: "Archived" },
];
const STATUS_TONE = { active: "success", draft: "neutral", archived: "neutral", removed: "danger" } as const;
// "removed" = taken down by moderation; only the Queneth team can restore it.
const STATUS_LABEL = { active: "Live", draft: "Draft", archived: "Archived", removed: "Taken down" } as const;

/** UX: Doherty Threshold — search filters as you type; bulk actions appear only when rows are selected. */
export function ProductsView() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>(null);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const list = useStudioProducts(tab, q);
  const { archive, duplicate, remove } = useProductActions();
  const counts = list.data?.counts ?? {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const rows = list.data?.items ?? [];
  const allOn = rows.length > 0 && rows.every((r) => selected.includes(r.id));

  const bulk = async (restore: boolean) => {
    try {
      const res = await archive.mutateAsync({ ids: selected, restore });
      toast.success(`${res.updated} ${res.updated === 1 ? "piece" : "pieces"} ${restore ? "restored" : "archived"}`);
      setSelected([]);
    } catch (err) {
      toast.error(toApiError(err).message);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Catalog</p>
          <h1 className="text-h1 text-ink">My products</h1>
        </div>
        <Button asChild variant="primary"><Link href="/seller/products/new"><Plus aria-hidden /> Add a product</Link></Button>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label="Filter by status" className="flex flex-wrap gap-2">
          {TABS.map((t) => {
            const n = t.value ? counts[t.value] ?? 0 : total;
            return (
              <button key={t.label} role="tab" aria-selected={tab === t.value} onClick={() => { setTab(t.value); setSelected([]); }}
                className={cn("inline-flex h-11 items-center gap-2 rounded-pill border px-4 text-small font-semibold", tab === t.value ? "border-ink bg-ink text-bg" : "border-border-strong text-ink hover:bg-surface-muted")}>
                {t.label} <span className="tabular text-caption opacity-80">{n}</span>
              </button>
            );
          })}
        </div>
        <label className="relative ml-auto w-full sm:w-72">
          <span className="sr-only">Search your products</span>
          <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-muted" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title" className="pl-9" />
        </label>
      </div>

      {selected.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-input border border-accent-2/40 bg-accent-2/5 px-4 py-2 text-small" role="status">
          <span className="font-semibold text-ink">{selected.length} selected</span>
          <Button size="sm" variant="outline" loading={archive.isPending} onClick={() => bulk(false)}><Archive aria-hidden /> Archive</Button>
          <Button size="sm" variant="outline" loading={archive.isPending} onClick={() => bulk(true)}><ArchiveRestore aria-hidden /> Restore</Button>
          <button type="button" onClick={() => setSelected([])} className="ml-auto min-h-11 font-semibold text-ink-muted hover:text-ink">Clear</button>
        </div>
      )}

      {list.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading products">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-16 rounded-input" />)}</div>
      ) : list.isError ? (
        <ErrorState message={toApiError(list.error).message} onRetry={() => list.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={PackageOpen}
          title={q ? `Nothing matches “${q}”` : tab === "draft" ? "No drafts" : tab === "archived" ? "Nothing archived" : "No pieces yet"}
          description={q ? "Try another word from the title." : "Start the wizard to add your first piece. It saves as you go."}
          action={!q ? <Button asChild variant="primary"><Link href="/seller/products/new">Add a product</Link></Button> : undefined}
        />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-small">
            <thead className="border-b border-border text-left text-ink-muted">
              <tr>
                <th className="w-12 px-4 py-3">
                  <Checkbox aria-label="Select all" checked={allOn} onCheckedChange={(v) => setSelected(v === true ? rows.map((r) => r.id) : [])} />
                </th>
                <th className="py-3 font-semibold">Product</th>
                <th className="py-3 font-semibold">Status</th>
                <th className="whitespace-nowrap px-3 py-3 text-right font-semibold">Price</th>
                <th className="whitespace-nowrap px-3 py-3 text-right font-semibold">Stock</th>
                <th className="whitespace-nowrap px-3 py-3 text-right font-semibold">Views · Saves · Sold</th>
                <th className="w-40 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border last:border-0 hover:bg-surface-muted/50">
                  <td className="px-4 py-3">
                    <Checkbox aria-label={`Select ${r.title}`} checked={selected.includes(r.id)} onCheckedChange={(v) => setSelected((s) => (v === true ? [...s, r.id] : s.filter((x) => x !== r.id)))} />
                  </td>
                  <td className="py-3">
                    <Link href={`/seller/products/${r.id}`} className="flex items-center gap-3 font-semibold text-ink hover:underline">
                      <span className="relative aspect-[4/5] w-10 shrink-0 overflow-clip rounded-input bg-surface-muted">
                        {r.image && <Image src={r.image} alt="" fill sizes="40px" className="object-cover" />}
                      </span>
                      <span className="flex flex-col">
                        {r.title}
                        <span className="text-caption font-normal capitalize text-ink-muted">{r.category} · {r.variant_count} {r.variant_count === 1 ? "variant" : "variants"}</span>
                      </span>
                    </Link>
                  </td>
                  <td className="py-3"><Badge tone={STATUS_TONE[r.status]} withIcon={false}>{STATUS_LABEL[r.status]}</Badge></td>
                  <td className="tabular whitespace-nowrap px-3 py-3 text-right">{r.min_price_qc ? formatQc(r.min_price_qc) : "—"}</td>
                  <td className={cn("tabular whitespace-nowrap px-3 py-3 text-right", r.low_stock && r.status === "active" && "font-semibold text-warning")}>{formatNumber(r.total_stock)}</td>
                  <td className="tabular whitespace-nowrap px-3 py-3 text-right text-ink-muted">{formatNumber(r.view_count)} · {formatNumber(r.wishlist_count)} · <span className="text-ink">{formatNumber(r.sold)}</span></td>
                  <td className="py-3 pr-2">
                    <div className="flex justify-end">
                      <Button asChild size="icon" variant="ghost" aria-label={`Edit ${r.title}`}><Link href={`/seller/products/${r.id}`}><Pencil aria-hidden /></Link></Button>
                      <Button size="icon" variant="ghost" aria-label={`Duplicate ${r.title}`} disabled={duplicate.isPending}
                        onClick={async () => {
                          try {
                            const copy = await duplicate.mutateAsync(r.id);
                            toast.success("Duplicated as a draft", { action: { label: "Open", onClick: () => router.push(`/seller/products/${copy.id}`) } });
                          } catch (err) {
                            toast.error(toApiError(err).message);
                          }
                        }}>
                        <Copy aria-hidden />
                      </Button>
                      {r.status === "draft" && (
                        <Button size="icon" variant="ghost" aria-label={`Delete draft ${r.title}`} className="text-ink-muted hover:text-danger"
                          onClick={() => remove.mutate(r.id, { onSuccess: () => toast.success("Draft deleted"), onError: (e) => toast.error(toApiError(e).message) })}>
                          <Trash2 aria-hidden />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
