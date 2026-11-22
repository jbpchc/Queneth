"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { toast } from "sonner";

import { api, toApiError, type ApiSchemas } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { useBagUi } from "@/lib/stores/bag-ui";

export type Bag = ApiSchemas["BagOut"];
const WISH_KEY = ["wishlist", "ids"] as const;
export const BAG_KEY = ["bag"] as const;

/** Saved product ids, for heart state on every card. */
export function useWishlistIds() {
  const { status, can } = useSession();
  return useQuery({
    queryKey: WISH_KEY,
    enabled: status === "authenticated" && can("wishlist:manage"),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/wishlist/ids");
      if (error || !data) throw error;
      return new Set(data.product_ids);
    },
    staleTime: 60_000,
  });
}

/**
 * UX: Doherty Threshold — optimistic: the heart fills instantly and rolls back
 * only if the API refuses. Guests are sent to sign in with a clear reason.
 */
export function useToggleWishlist() {
  const qc = useQueryClient();
  const router = useRouter();
  const { status } = useSession();
  const mutation = useMutation({
    mutationFn: async ({ id, saved }: { id: string; saved: boolean }) => {
      const res = saved
        ? await api.PUT("/api/v1/wishlist/{product_id}", { params: { path: { product_id: id } } })
        : await api.DELETE("/api/v1/wishlist/{product_id}", { params: { path: { product_id: id } } });
      if (res.error) throw res.error;
    },
    onMutate: async ({ id, saved }) => {
      await qc.cancelQueries({ queryKey: WISH_KEY });
      const previous = qc.getQueryData<Set<string>>(WISH_KEY);
      const next = new Set(previous ?? []);
      if (saved) next.add(id);
      else next.delete(id);
      qc.setQueryData(WISH_KEY, next);
      return { previous };
    },
    onError: (err, _vars, ctx) => {
      qc.setQueryData(WISH_KEY, ctx?.previous);
      toast.error("Couldn't update your wishlist", { description: toApiError(err).message });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["wishlist"], refetchType: "none" }),
  });

  return (id: string, saved: boolean): boolean => {
    if (status !== "authenticated") {
      toast("Sign in to save pieces", {
        description: "Your wishlist follows you across devices.",
        action: { label: "Sign in", onClick: () => router.push(`/login?next=${encodeURIComponent(location.pathname)}`) },
      });
      return false;
    }
    mutation.mutate({ id, saved });
    return true;
  };
}

/** The bag, kept in sync with the header badge. */
export function useBag() {
  const { status, can } = useSession();
  const setCount = useBagUi((s) => s.setCount);
  const query = useQuery({
    queryKey: BAG_KEY,
    enabled: status === "authenticated" && can("cart:manage"),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/cart");
      if (error || !data) throw error;
      return data;
    },
  });
  useEffect(() => {
    if (query.data) setCount(query.data.item_count);
    if (status === "guest") setCount(0);
  }, [query.data, status, setCount]);
  return query;
}

export function useAddToBag() {
  const qc = useQueryClient();
  const bump = useBagUi((s) => s.bump);
  const setCount = useBagUi((s) => s.setCount);
  return useMutation({
    mutationFn: async ({ variantId, qty = 1 }: { variantId: string; qty?: number }) => {
      const { data, error } = await api.POST("/api/v1/cart/items", { body: { variant_id: variantId, qty } });
      if (error || !data) throw error;
      return data;
    },
    // UX: Doherty Threshold — the badge bounces before the round trip finishes.
    onMutate: ({ qty = 1 }) => bump(qty),
    onSuccess: (bag) => {
      qc.setQueryData(BAG_KEY, bag);
      setCount(bag.item_count);
    },
    onError: () => qc.invalidateQueries({ queryKey: BAG_KEY }),
  });
}

export function useBagLine() {
  const qc = useQueryClient();
  const setCount = useBagUi((s) => s.setCount);
  const done = (bag: Bag) => {
    qc.setQueryData(BAG_KEY, bag);
    setCount(bag.item_count);
  };
  const setQty = useMutation({
    mutationFn: async ({ id, qty }: { id: string; qty: number }) => {
      const { data, error } = await api.PATCH("/api/v1/cart/items/{item_id}", {
        params: { path: { item_id: id } },
        body: { qty },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: done,
    onError: (err) => toast.error("Couldn't change quantity", { description: toApiError(err).message }),
  });
  const remove = useMutation({
    mutationFn: async (id: string) => {
      const { data, error } = await api.DELETE("/api/v1/cart/items/{item_id}", { params: { path: { item_id: id } } });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: done,
  });
  return { setQty, remove };
}
