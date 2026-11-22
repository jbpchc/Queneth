"use client";

import { ChevronRight, Package } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { statusLabel, statusTone, useOrders } from "@/lib/commerce";
import { formatQc } from "@/lib/format";

const dateFmt = new Intl.DateTimeFormat("en-PH", { dateStyle: "medium" });

export function OrdersList() {
  const orders = useOrders();

  if (orders.isPending) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading orders">
        {Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-28 rounded-card" />)}
      </div>
    );
  }
  if (orders.isError) {
    return <ErrorState message={toApiError(orders.error).message} onRetry={() => orders.refetch()} />;
  }
  const rows = orders.data.pages.flatMap((p) => p.items);
  if (rows.length === 0) {
    return (
      <EmptyState
        icon={Package}
        title="No orders yet"
        description="When you check out, your orders and their delivery progress appear here."
        action={<Button asChild variant="secondary"><Link href="/search?sort=newest">Browse new arrivals</Link></Button>}
      />
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-col gap-4">
        {rows.map((o) => (
          <li key={o.id}>
            {/* UX: Common Region — the whole card is one target (Fitts's Law). */}
            <Link href={`/account/orders/${o.id}`} className="block rounded-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-2">
              <Card className="flex items-center gap-4 p-4 transition-shadow hover:shadow-2 sm:p-5">
                <div className="flex shrink-0 -space-x-6">
                  {o.preview_images.slice(0, 3).map((src, i) => (
                    <div key={src + i} className="relative aspect-[4/5] w-14 overflow-hidden rounded-input border-2 border-surface bg-surface-muted">
                      <Image src={src} alt="" fill sizes="56px" className="object-cover" />
                    </div>
                  ))}
                </div>
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="tabular font-semibold text-ink">{o.number}</span>
                    <Badge tone={statusTone(o.status)} withIcon={false}>{statusLabel[o.status] ?? o.status}</Badge>
                  </div>
                  <p className="truncate text-small text-ink-muted">
                    {dateFmt.format(new Date(o.created_at))} · {o.item_count} {o.item_count === 1 ? "piece" : "pieces"} · {o.boutiques.join(", ")}
                  </p>
                </div>
                <span className="tabular hidden font-bold text-ink sm:inline">{formatQc(o.total_qc)}</span>
                <ChevronRight aria-hidden className="size-5 shrink-0 text-ink-muted" />
              </Card>
            </Link>
          </li>
        ))}
      </ul>
      {orders.hasNextPage && (
        <Button variant="outline" className="self-center" loading={orders.isFetchingNextPage} onClick={() => orders.fetchNextPage()}>
          Show older orders
        </Button>
      )}
    </div>
  );
}
