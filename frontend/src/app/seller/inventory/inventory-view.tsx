"use client";

import { Boxes } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { formatQc } from "@/lib/format";
import { useInventory, useUpdateInventory } from "@/lib/studio";
import { cn } from "@/lib/utils";

type Edit = { stock?: string; threshold?: string };

/**
 * Every variant's stock in one table, edited inline and saved together.
 * UX: Doherty Threshold — edits are instant locally; one Save sends them all.
 * UX: Von Restorff — only rows at or below their alert level are highlighted.
 */
export function InventoryView() {
  const [low, setLow] = useState(false);
  const inv = useInventory(low);
  const save = useUpdateInventory();
  const [edits, setEdits] = useState<Record<string, Edit>>({});

  const changed = useMemo(() => {
    const rows = inv.data ?? [];
    return Object.entries(edits).flatMap(([id, e]) => {
      const row = rows.find((r) => r.variant_id === id);
      if (!row) return [];
      const stock = e.stock !== undefined && e.stock !== "" ? Number(e.stock) : undefined;
      const threshold = e.threshold !== undefined && e.threshold !== "" ? Number(e.threshold) : undefined;
      if ((stock === undefined || stock === row.stock) && (threshold === undefined || threshold === row.low_stock_threshold)) return [];
      return [{ variant_id: id, ...(stock !== undefined ? { stock } : {}), ...(threshold !== undefined ? { low_stock_threshold: threshold } : {}) }];
    });
  }, [edits, inv.data]);

  const set = (id: string, p: Edit) => setEdits((all) => ({ ...all, [id]: { ...all[id], ...p } }));

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Stock</p>
          <h1 className="text-h1 text-ink">Stock</h1>
        </div>
        <label className="flex min-h-11 items-center gap-3 text-small font-semibold text-ink">
          <Switch checked={low} onCheckedChange={(v) => setLow(v === true)} />
          Low stock only
        </label>
      </header>

      {inv.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading inventory">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-14 rounded-input" />)}</div>
      ) : inv.isError ? (
        <ErrorState message={toApiError(inv.error).message} onRetry={() => inv.refetch()} />
      ) : inv.data.length === 0 ? (
        <EmptyState
          icon={Boxes}
          title={low ? "Nothing is running low" : "No variants yet"}
          description={low ? "Every live variant is above its alert level." : "Variants appear here once you add a piece."}
          action={!low ? <Button asChild variant="primary"><Link href="/seller/products/new">Add a product</Link></Button> : undefined}
        />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-small">
            <thead className="border-b border-border text-left text-ink-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">Product</th>
                <th className="py-3 font-semibold">SKU</th>
                <th className="py-3 text-right font-semibold">Price</th>
                <th className="w-28 py-3 text-right font-semibold">Stock</th>
                <th className="w-28 py-3 pr-4 text-right font-semibold">Alert at</th>
              </tr>
            </thead>
            <tbody>
              {inv.data.map((r) => {
                const e = edits[r.variant_id] ?? {};
                const stock = e.stock ?? String(r.stock);
                const isLow = Number(stock) <= Number(e.threshold ?? r.low_stock_threshold);
                return (
                  <tr key={r.variant_id} className={cn("border-b border-border last:border-0", isLow && r.product_status === "active" && "bg-warning-soft/40")}>
                    <td className="px-4 py-2.5">
                      <Link href={`/seller/products/${r.product_id}?step=variants`} className="flex items-center gap-3 hover:underline">
                        <span className="relative aspect-[4/5] w-9 shrink-0 overflow-clip rounded-input bg-surface-muted">
                          {r.image && <Image src={r.image} alt="" fill sizes="36px" className="object-cover" />}
                        </span>
                        <span className="flex flex-col">
                          <span className="font-semibold text-ink">{r.product_title}</span>
                          <span className="text-caption text-ink-muted">{Object.values(r.options).join(" · ")}{r.product_status !== "active" && ` · ${r.product_status}`}</span>
                        </span>
                      </Link>
                    </td>
                    <td className="tabular py-2.5 text-ink-muted">{r.sku}</td>
                    <td className="tabular py-2.5 text-right">{formatQc(r.price_qc)}</td>
                    <td className="py-2.5 text-right">
                      <Input aria-label={`Stock for ${r.product_title} ${Object.values(r.options).join(" ")}`} inputMode="numeric" value={stock}
                        onChange={(ev) => set(r.variant_id, { stock: ev.target.value.replace(/\D/g, "").slice(0, 4) })} className="tabular h-10 w-24 text-right" />
                    </td>
                    <td className="py-2.5 pr-4 text-right">
                      <Input aria-label={`Low-stock alert for ${r.product_title}`} inputMode="numeric" value={e.threshold ?? String(r.low_stock_threshold)}
                        onChange={(ev) => set(r.variant_id, { threshold: ev.target.value.replace(/\D/g, "").slice(0, 3) })} className="tabular h-10 w-24 text-right" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}

      {changed.length > 0 && (
        <div className="sticky bottom-0 -mx-4 flex items-center justify-end gap-3 border-t border-border bg-bg/95 px-4 py-4 backdrop-blur" role="status">
          <span className="mr-auto text-small text-ink-muted">{changed.length} unsaved {changed.length === 1 ? "change" : "changes"}</span>
          <Button variant="ghost" onClick={() => setEdits({})}>Discard</Button>
          <Button variant="primary" loading={save.isPending}
            onClick={async () => {
              try {
                await save.mutateAsync(changed);
                setEdits({});
                toast.success("Inventory updated");
              } catch (err) {
                toast.error(toApiError(err).message);
              }
            }}>
            Save {changed.length} {changed.length === 1 ? "change" : "changes"}
          </Button>
        </div>
      )}
    </div>
  );
}
