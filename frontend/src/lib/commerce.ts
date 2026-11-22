"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, toApiError, type ApiSchemas } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { BAG_KEY, type Bag } from "@/lib/shop";
import { useBagUi } from "@/lib/stores/bag-ui";

export type Address = ApiSchemas["AddressOut"];
export type AddressInput = ApiSchemas["AddressIn"];
export type Board = ApiSchemas["BoardOut"];
export type Order = ApiSchemas["OrderOut"];
export type OrderSummary = ApiSchemas["OrderSummary"];

const ADDRESSES = ["addresses"] as const;

// ─── Address book ──────────────────────────────────────────────────────────

export function useAddresses() {
  const { status } = useSession();
  return useQuery({
    queryKey: ADDRESSES,
    enabled: status === "authenticated",
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/addresses");
      if (error || !data) throw error;
      return data;
    },
  });
}

export function useAddressMutations() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ADDRESSES });
  const save = useMutation({
    mutationFn: async ({ id, body }: { id?: string; body: AddressInput }) => {
      const res = id
        ? await api.PUT("/api/v1/addresses/{address_id}", { params: { path: { address_id: id } }, body })
        : await api.POST("/api/v1/addresses", { body });
      if (res.error || !res.data) throw res.error;
      return res.data;
    },
    onSuccess: refresh,
  });
  const makeDefault = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await api.POST("/api/v1/addresses/{address_id}/default", {
        params: { path: { address_id: id } },
      });
      if (error) throw error;
    },
    onSuccess: refresh,
    onError: (err) => toast.error("Couldn't change your default", { description: toApiError(err).message }),
  });
  const remove = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await api.DELETE("/api/v1/addresses/{address_id}", {
        params: { path: { address_id: id } },
      });
      if (error) throw error;
    },
    onSuccess: refresh,
    onError: (err) => toast.error("Couldn't delete that address", { description: toApiError(err).message }),
  });
  return { save, makeDefault, remove };
}

/** "18 Amorsolo St., Bel-Air, City of Makati, NCR 1209" */
export function addressLine(a: {
  line1?: string | null;
  barangay?: string | null;
  city?: string | null;
  province?: string | null;
  zip?: string | null;
}): string {
  return [a.line1, a.barangay, a.city, a.province].filter(Boolean).join(", ") + (a.zip ? ` ${a.zip}` : "");
}

/** "+639171234567" → "0917 123 4567" (UX: Miller's Law — chunked). */
export function formatPhone(e164: string | null | undefined): string {
  if (!e164) return "";
  const d = e164.replace(/^\+63/, "0");
  return d.length === 11 ? `${d.slice(0, 4)} ${d.slice(4, 7)} ${d.slice(7)}` : e164;
}

// ─── Bag: save for later & vouchers ────────────────────────────────────────

function useBagSetter() {
  const qc = useQueryClient();
  const setCount = useBagUi((s) => s.setCount);
  return (bag: Bag) => {
    qc.setQueryData(BAG_KEY, bag);
    setCount(bag.item_count);
  };
}

export function useSaveForLater() {
  const done = useBagSetter();
  return useMutation({
    mutationFn: async ({ id, saved }: { id: string; saved: boolean }) => {
      const { data, error } = await api.PUT("/api/v1/cart/items/{item_id}/saved", {
        params: { path: { item_id: id } },
        body: { saved },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: done,
    onError: (err) => toast.error("Couldn't move that piece", { description: toApiError(err).message }),
  });
}

export function useVouchers() {
  const done = useBagSetter();
  const apply = useMutation({
    mutationFn: async (code: string) => {
      const { data, error } = await api.POST("/api/v1/cart/vouchers", { body: { code } });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: done,
  });
  const remove = useMutation({
    mutationFn: async (voucherId: string) => {
      const { data, error } = await api.DELETE("/api/v1/cart/vouchers/{voucher_id}", {
        params: { path: { voucher_id: voucherId } },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: done,
  });
  return { apply, remove };
}

// ─── Wishlist boards ───────────────────────────────────────────────────────

export function useBoardMutations() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["wishlist"] });
  const create = useMutation({
    mutationFn: async (name: string) => {
      const { data, error } = await api.POST("/api/v1/wishlist/boards", { body: { name } });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: refresh,
  });
  const rename = useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) => {
      const { data, error } = await api.PATCH("/api/v1/wishlist/boards/{board_id}", {
        params: { path: { board_id: id } },
        body: { name },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await api.DELETE("/api/v1/wishlist/boards/{board_id}", {
        params: { path: { board_id: id } },
      });
      if (error) throw error;
    },
    onSuccess: refresh,
    onError: (err) => toast.error("Couldn't delete that board", { description: toApiError(err).message }),
  });
  const move = useMutation({
    mutationFn: async ({ productId, boardId }: { productId: string; boardId: string | null }) => {
      const { error } = await api.PUT("/api/v1/wishlist/{product_id}/board", {
        params: { path: { product_id: productId } },
        body: { board_id: boardId },
      });
      if (error) throw error;
    },
    onSuccess: refresh,
    onError: (err) => toast.error("Couldn't move that piece", { description: toApiError(err).message }),
  });
  return { create, rename, remove, move };
}

// ─── Checkout & orders ─────────────────────────────────────────────────────

export function useCheckout() {
  const qc = useQueryClient();
  const setCount = useBagUi((s) => s.setCount);
  return useMutation({
    mutationFn: async (vars: { addressId: string; pin: string; total: number; key: string }) => {
      const { data, error } = await api.POST("/api/v1/orders/checkout", {
        body: { address_id: vars.addressId, pin: vars.pin, expected_total_qc: vars.total },
        params: { header: { "Idempotency-Key": vars.key } },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: (order) => {
      qc.setQueryData(["orders", order.id], order);
      qc.invalidateQueries({ queryKey: BAG_KEY });
      qc.invalidateQueries({ queryKey: ["wallet"] });
      qc.invalidateQueries({ queryKey: ["orders", "list"] });
      qc.invalidateQueries({ queryKey: ["notifications"] });
      setCount(0);
    },
  });
}

export function useOrder(id: string) {
  const { status } = useSession();
  return useQuery({
    queryKey: ["orders", id],
    enabled: status === "authenticated",
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } });
      if (error || !data) throw error;
      return data;
    },
  });
}

export function useOrders() {
  const { status } = useSession();
  return useInfiniteQuery({
    queryKey: ["orders", "list"],
    enabled: status === "authenticated",
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.GET("/api/v1/orders", {
        params: { query: { limit: 10, ...(pageParam ? { cursor: pageParam } : {}) } },
      });
      if (error || !data) throw error;
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}

export const statusLabel: Record<string, string> = {
  PAID: "Paid · in escrow",
  PROCESSING: "Preparing",
  SHIPPED: "Shipped",
  DELIVERED: "Delivered",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
  RETURN_REQUESTED: "Return requested",
  REFUNDED: "Refunded",
};

// ─── Order actions (buyer) ─────────────────────────────────────────────────

export type SubOrder = ApiSchemas["SubOrderOut"];
export type OrderItem = ApiSchemas["OrderItemOut"];

/** Cancel, mark received or request a return; the server returns the fresh order. */
export function useOrderActions(orderId: string) {
  const qc = useQueryClient();
  const settle = (order: Order) => {
    qc.setQueryData(["orders", orderId], order);
    qc.invalidateQueries({ queryKey: ["orders", "list"] });
    qc.invalidateQueries({ queryKey: ["wallet"] });
    qc.invalidateQueries({ queryKey: ["notifications"] });
  };
  const cancel = useMutation({
    mutationFn: async ({ subId, reason }: { subId: string; reason?: string }) => {
      const { data, error } = await api.POST("/api/v1/orders/sub-orders/{sub_id}/cancel", {
        params: { path: { sub_id: subId } },
        body: { reason: reason || null },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: settle,
  });
  const received = useMutation({
    mutationFn: async (subId: string) => {
      const { data, error } = await api.POST("/api/v1/orders/sub-orders/{sub_id}/received", {
        params: { path: { sub_id: subId } },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: settle,
  });
  const requestReturn = useMutation({
    mutationFn: async ({ subId, reason }: { subId: string; reason: string }) => {
      const { data, error } = await api.POST("/api/v1/orders/sub-orders/{sub_id}/return", {
        params: { path: { sub_id: subId } },
        body: { reason },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: settle,
  });
  return { cancel, received, requestReturn };
}

export function useCreateReview(orderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ApiSchemas["ReviewIn"]) => {
      const { data, error } = await api.POST("/api/v1/reviews", { body });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders", orderId] }),
  });
}

// ─── Seller fulfilment queue ───────────────────────────────────────────────

export type SellerOrder = ApiSchemas["SellerSubOrder"];
export type SubStatus = ApiSchemas["TransitionRequest"]["to"];

export function useSellerOrders(status: SubStatus | null) {
  const { status: auth } = useSession();
  return useInfiniteQuery({
    queryKey: ["seller", "orders", status],
    enabled: auth === "authenticated",
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.GET("/api/v1/seller/orders", {
        params: { query: { ...(status ? { status } : {}), ...(pageParam ? { cursor: pageParam } : {}) } },
      });
      if (error || !data) throw error;
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}

export function useSellerMove() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { subId: string; to: SubStatus; note?: string; trackingNo?: string }) => {
      const { data, error } = await api.POST("/api/v1/seller/orders/{sub_id}/status", {
        params: { path: { sub_id: vars.subId } },
        body: { to: vars.to, note: vars.note || null, tracking_no: vars.trackingNo || null },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["seller", "orders"] });
      qc.invalidateQueries({ queryKey: ["wallet"] });
    },
  });
}

/** A plausible simulated courier reference: "QNX-4821-7730". */
export function simulatedTracking(): string {
  const n = () => Math.floor(1000 + Math.random() * 9000);
  return `QNX-${n()}-${n()}`;
}

/** Badge tone per status. Color is never the only signal: the label says it too. */
export function statusTone(status: string): "info" | "success" | "warning" | "neutral" {
  if (status === "DELIVERED" || status === "COMPLETED") return "success";
  if (status === "RETURN_REQUESTED") return "warning";
  if (status === "CANCELLED" || status === "REFUNDED") return "neutral";
  return "info";
}
