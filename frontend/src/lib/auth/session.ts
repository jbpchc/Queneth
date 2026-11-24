"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { api, type ApiSchemas } from "@/lib/api/client";

export type Me = ApiSchemas["MeOut"];
export type Role = Me["roles"][number];
export const ME_KEY = ["me"] as const;
const noop = () => () => {};

/**
 * The signed-in user, `null` for guests. Permissions come from the API so the
 * UI can hide controls it knows will be refused; the API still enforces them.
 */
export function useSession() {
  const query = useQuery({
    queryKey: ME_KEY,
    queryFn: async (): Promise<Me | null> => {
      const { data, error, response } = await api.GET("/api/v1/me");
      if (response.status === 401 || response.status === 403) return null;
      if (error) throw error;
      return data ?? null;
    },
    staleTime: 60_000,
  });
  // The server renders every page as "loading" (it has no session). Parts of a
  // page can hydrate late (streaming), after /me has resolved, so report
  // "loading" while hydrating too; otherwise React sees a mismatch.
  const hydrated = useSyncExternalStore(noop, () => true, () => false);
  const user = hydrated ? (query.data ?? null) : null;
  return {
    user,
    status: !hydrated || query.isPending ? "loading" : user ? "authenticated" : "guest",
    hasRole: (role: Role) => !!user?.roles.includes(role),
    can: (permission: string) => !!user?.permissions.includes(permission),
    /** Guests and buyer accounts shop; seller and admin accounts never do. */
    shopper: !user || user.permissions.includes("cart:manage"),
    refetch: query.refetch,
  } as const;
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ApiSchemas["LoginRequest"]) => {
      const { data, error } = await api.POST("/api/v1/auth/login", { body });
      if (error) throw error;
      return data.user;
    },
    onSuccess: (user) => qc.setQueryData(ME_KEY, user),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ApiSchemas["RegisterRequest"]) => {
      const { data, error } = await api.POST("/api/v1/auth/register", { body });
      if (error || !data) throw error;
      return data.user;
    },
    onSuccess: (user) => qc.setQueryData(ME_KEY, user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/auth/logout");
    },
    onSettled: () => {
      qc.setQueryData(ME_KEY, null);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
    },
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ApiSchemas["MeUpdate"]) => {
      const { data, error } = await api.PATCH("/api/v1/me", { body });
      if (error) throw error;
      return data;
    },
    onSuccess: (user) => qc.setQueryData(ME_KEY, user),
  });
}

/** Where to land after sign-in when there's no ?next=. */
export function homeFor(user: Me): string {
  if (user.roles.includes("ADMIN")) return "/admin";
  if (user.roles.includes("SELLER")) return "/seller";
  return "/";
}

/**
 * Where to go after signing in. Shoppers return to where they were; seller and
 * admin accounts only follow `next` inside their own area (a seller sent to
 * /bag by an old link lands in Seller Studio instead).
 */
export function landingFor(user: Me, next: string | null): string | null {
  const home = homeFor(user);
  if (user.roles.includes("BUYER")) return next;
  return next && (next === home || next.startsWith(`${home}/`) || next.startsWith("/account")) ? next : home;
}
