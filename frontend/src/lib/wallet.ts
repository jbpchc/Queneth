"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type ApiSchemas } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";

export type WalletSummary = ApiSchemas["WalletSummary"];
export type LedgerLine = ApiSchemas["LedgerLine"];
export type WalletCategory = "payments" | "refunds" | "topups" | "earnings";

const WALLET = ["wallet"] as const;

/** A fresh idempotency key per attempt; reuse it to retry the same attempt safely. */
export const newKey = () => crypto.randomUUID();

export function useWallet() {
  const { status, can } = useSession();
  return useQuery({
    queryKey: [...WALLET, "summary"],
    enabled: status === "authenticated" && can("wallet:view"),
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/wallet");
      if (error || !data) throw error;
      return data;
    },
  });
}

export function useWalletHistory(category: WalletCategory | null) {
  const { status } = useSession();
  return useInfiniteQuery({
    queryKey: [...WALLET, "history", category],
    enabled: status === "authenticated",
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data, error } = await api.GET("/api/v1/wallet/transactions", {
        params: { query: { ...(category ? { category } : {}), ...(pageParam ? { cursor: pageParam } : {}), limit: 12 } },
      });
      if (error || !data) throw error;
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}

/** After any money movement: update the balance at once, refresh history. */
function useSettle() {
  const qc = useQueryClient();
  return (result: ApiSchemas["TxResult"]) => {
    qc.setQueryData([...WALLET, "summary"], result.wallet);
    qc.invalidateQueries({ queryKey: [...WALLET, "history"] });
    qc.invalidateQueries({ queryKey: ["notifications"] });
  };
}

export function useTopUp() {
  const settle = useSettle();
  return useMutation({
    mutationFn: async ({ amount, key }: { amount: number; key: string }) => {
      const { data, error } = await api.POST("/api/v1/wallet/topups", {
        body: { amount_qc: amount },
        params: { header: { "Idempotency-Key": key } },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: settle,
  });
}

export function useRedeem() {
  const settle = useSettle();
  return useMutation({
    mutationFn: async (code: string) => {
      const { data, error } = await api.POST("/api/v1/wallet/redeem", { body: { code } });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: settle,
  });
}

export function useWithdraw() {
  const settle = useSettle();
  return useMutation({
    mutationFn: async ({ amount, pin, key }: { amount: number; pin: string; key: string }) => {
      const { data, error } = await api.POST("/api/v1/wallet/withdrawals", {
        body: { amount_qc: amount, pin },
        params: { header: { "Idempotency-Key": key } },
      });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: settle,
  });
}

export function usePin() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: [...WALLET, "summary"] });
  const setPin = useMutation({
    mutationFn: async (pin: string) => {
      const { error } = await api.POST("/api/v1/wallet/pin", { body: { pin } });
      if (error) throw error;
    },
    onSettled: refresh,
  });
  const changePin = useMutation({
    mutationFn: async ({ current, next }: { current: string; next: string }) => {
      const { error } = await api.PUT("/api/v1/wallet/pin", { body: { current_pin: current, new_pin: next } });
      if (error) throw error;
    },
    onSettled: refresh,
  });
  return { setPin, changePin };
}
