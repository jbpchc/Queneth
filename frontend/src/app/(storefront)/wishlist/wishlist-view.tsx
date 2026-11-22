"use client";

import { useQuery } from "@tanstack/react-query";
import { Heart, Pencil, Plus, Trash2, TrendingDown } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { ProductCard } from "@/components/catalog/product-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ProductCardSkeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { api, toApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { useBoardMutations, type Board } from "@/lib/commerce";
import { formatQc } from "@/lib/format";
import { useWishlistIds } from "@/lib/shop";

/**
 * Saved pieces with honest price-drop and availability indicators, filed on
 * named boards. UX: Chunking — boards split a long wishlist into small sets.
 */
export function WishlistView() {
  const { status, can } = useSession();
  const ids = useWishlistIds();
  const { move } = useBoardMutations();
  const [board, setBoard] = useState<string | null>(null);
  const list = useQuery({
    queryKey: ["wishlist", "items"],
    enabled: status === "authenticated" && can("wishlist:manage"),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/wishlist");
      if (error || !data) throw error;
      return data;
    },
  });

  const header = (
    <header className="mb-8 flex flex-col gap-2">
      <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Saved for later</p>
      <h1 className="text-h1 text-ink">Wishlist</h1>
    </header>
  );

  if (status === "guest") {
    return (
      <>
        {header}
        <EmptyState
          icon={Heart}
          title="Sign in to keep a wishlist"
          description="Save pieces with the heart and they'll follow you across devices, with alerts when prices drop."
          action={<Button asChild variant="primary"><Link href="/login?next=/wishlist">Sign in</Link></Button>}
        />
      </>
    );
  }
  if (status === "loading" || list.isPending) {
    return (
      <>
        {header}
        <div className="grid grid-cols-2 gap-x-4 gap-y-10 sm:grid-cols-3 lg:grid-cols-4" aria-busy="true" aria-label="Loading wishlist">
          {Array.from({ length: 4 }, (_, i) => <ProductCardSkeleton key={i} />)}
        </div>
      </>
    );
  }
  if (list.isError) {
    return (<>{header}<ErrorState message={toApiError(list.error).message} onRetry={() => list.refetch()} /></>);
  }

  // Hearts toggled off on this page disappear immediately (optimistic ids).
  const all = list.data.items.filter((e) => ids.data?.has(e.product.id) ?? true);
  const boards = list.data.boards;
  const current = boards.find((b) => b.id === board) ?? null;
  const items = current ? all.filter((e) => e.board_id === current.id) : all;
  return (
    <>
      {header}
      {all.length > 0 && (
        <BoardBar boards={boards} total={all.length} current={current} onSelect={setBoard} />
      )}
      {current && items.length === 0 ? (
        <EmptyState
          icon={Heart}
          title={`Nothing on ${current.name} yet`}
          description="File saved pieces here with the board menu under each one."
          action={<Button variant="outline" onClick={() => setBoard(null)}>See all saved</Button>}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Heart}
          title="Your wishlist is waiting"
          description="Tap the heart on anything that catches your eye. Isabela keeps one for every season."
          action={<Button asChild variant="secondary"><Link href="/search?sort=newest">Browse new arrivals</Link></Button>}
        />
      ) : (
        <ul className="grid grid-cols-2 gap-x-4 gap-y-10 sm:grid-cols-3 lg:grid-cols-4">
          {items.map((e) => (
            <li key={e.product.id} className="flex flex-col gap-2">
              <ProductCard card={e.product} />
              <div className="flex flex-wrap gap-1.5">
                {e.price_dropped && e.saved_price_qc && (
                  <Badge tone="tangerine" withIcon={false} className="gap-1">
                    <TrendingDown aria-hidden /> Down from {formatQc(e.saved_price_qc)}
                  </Badge>
                )}
                {!e.available && <Badge tone="neutral" withIcon={false}>Currently unavailable</Badge>}
              </div>
              {boards.length > 0 && (
                <Select
                  aria-label={`Board for ${e.product.title}`}
                  value={e.board_id ?? ""}
                  onChange={(ev) => move.mutate({ productId: e.product.id, boardId: ev.target.value || null })}
                  className="h-11 text-small"
                >
                  <option value="">No board</option>
                  {boards.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </Select>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function BoardBar({
  boards,
  total,
  current,
  onSelect,
}: {
  boards: Board[];
  total: number;
  current: Board | null;
  onSelect: (id: string | null) => void;
}) {
  const { create, rename, remove } = useBoardMutations();
  const [mode, setMode] = useState<"idle" | "new" | "rename">("idle");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError(null);
    try {
      if (mode === "rename" && current) {
        await rename.mutateAsync({ id: current.id, name });
      } else {
        const b = await create.mutateAsync(name);
        onSelect(b.id);
        toast.success(`Board "${b.name}" created`);
      }
      setMode("idle");
      setName("");
    } catch (err) {
      setError(toApiError(err).message);
    }
  };

  return (
    <div className="mb-8 flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Boards">
        <Chip selected={current === null} onClick={() => onSelect(null)}>All saved · {total}</Chip>
        {boards.map((b) => (
          <Chip key={b.id} selected={current?.id === b.id} onClick={() => onSelect(b.id)}>
            {b.name} · {b.count}
          </Chip>
        ))}
        <Button variant="ghost" size="sm" onClick={() => { setMode("new"); setName(""); setError(null); }}>
          <Plus aria-hidden /> New board
        </Button>
        {current && (
          <>
            <Button variant="ghost" size="sm" onClick={() => { setMode("rename"); setName(current.name); setError(null); }}>
              <Pencil aria-hidden /> Rename
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-ink-muted hover:text-danger"
              onClick={() =>
                remove.mutate(current.id, {
                  onSuccess: () => {
                    onSelect(null);
                    toast.success(`Board "${current.name}" deleted`, { description: "Its pieces are still saved." });
                  },
                })
              }
            >
              <Trash2 aria-hidden /> Delete board
            </Button>
          </>
        )}
      </div>
      {mode !== "idle" && (
        <form onSubmit={submit} className="flex max-w-md flex-col gap-2" noValidate>
          <label htmlFor="board-name" className="text-small font-semibold text-ink">
            {mode === "new" ? "Board name" : "New name"}
          </label>
          <div className="flex gap-2">
            <Input id="board-name" value={name} maxLength={48} autoFocus placeholder="e.g. Wedding season" onChange={(e) => setName(e.target.value)} aria-invalid={error ? true : undefined} />
            <Button type="submit" variant="secondary" loading={create.isPending || rename.isPending}>Save</Button>
            <Button type="button" variant="ghost" onClick={() => setMode("idle")}>Cancel</Button>
          </div>
          {error && <p role="alert" className="text-small text-danger">{error}</p>}
        </form>
      )}
    </div>
  );
}
