"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type ApiSchemas } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";

export type Overview = ApiSchemas["Overview"];
export type AdminSeller = ApiSchemas["AdminSeller"];
export type AdminUserRow = ApiSchemas["AdminUserRow"];
export type AdminUserDetail = ApiSchemas["AdminUserDetail"];
export type AdminCategory = ApiSchemas["AdminCategory"];
export type AdminCollection = ApiSchemas["AdminCollection"];
export type FlagGroup = ApiSchemas["FlagGroup"];
export type AdminTx = ApiSchemas["AdminTxOut"];
export type AuditEntry = ApiSchemas["AuditLogOut"];
export type AdminPromotion = ApiSchemas["PromotionOut"];
export type PromotionIn = ApiSchemas["PromotionIn"];

async function unwrap<T>(p: Promise<{ data?: T; error?: unknown }>): Promise<T> {
  const { data, error } = await p;
  if (error !== undefined) throw error;
  return data as T;
}

function useAdmin() {
  const { status, hasRole } = useSession();
  return status === "authenticated" && hasRole("ADMIN");
}

const K = {
  overview: ["admin", "overview"] as const,
  sellers: ["admin", "sellers"] as const,
  users: ["admin", "users"] as const,
  catalog: ["admin", "catalog"] as const,
  moderation: ["admin", "moderation"] as const,
  wallet: ["admin", "wallet"] as const,
  audit: ["admin", "audit"] as const,
  promotions: ["admin", "promotions"] as const,
};

// ─── Overview ──────────────────────────────────────────────────────────────

export function useOverview() {
  const on = useAdmin();
  return useQuery({ queryKey: K.overview, enabled: on, queryFn: () => unwrap(api.GET("/api/v1/admin/overview")) });
}

// ─── Sellers ───────────────────────────────────────────────────────────────

export type SellerStatus = "pending" | "approved" | "rejected" | "suspended";

export function useAdminSellers(status: SellerStatus | null, q: string) {
  const on = useAdmin();
  return useQuery({
    queryKey: [...K.sellers, status, q],
    enabled: on,
    placeholderData: (prev) => prev,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/sellers", {
          params: { query: { ...(status ? { status } : {}), ...(q.trim() ? { q: q.trim() } : {}) } },
        }),
      ),
  });
}

export function useSellerActions() {
  const qc = useQueryClient();
  const settle = () => {
    qc.invalidateQueries({ queryKey: K.sellers });
    qc.invalidateQueries({ queryKey: K.overview });
    qc.invalidateQueries({ queryKey: K.audit });
  };
  const path = (seller_id: string) => ({ params: { path: { seller_id } } });
  return {
    approve: useMutation({
      mutationFn: (id: string) => unwrap(api.POST("/api/v1/admin/sellers/{seller_id}/approve", path(id))),
      onSuccess: settle,
    }),
    reject: useMutation({
      mutationFn: ({ id, reason }: { id: string; reason: string }) =>
        unwrap(api.POST("/api/v1/admin/sellers/{seller_id}/reject", { ...path(id), body: { reason } })),
      onSuccess: settle,
    }),
    suspend: useMutation({
      mutationFn: ({ id, reason }: { id: string; reason: string }) =>
        unwrap(api.POST("/api/v1/admin/sellers/{seller_id}/suspend", { ...path(id), body: { reason } })),
      onSuccess: settle,
    }),
    reinstate: useMutation({
      mutationFn: (id: string) => unwrap(api.POST("/api/v1/admin/sellers/{seller_id}/reinstate", path(id))),
      onSuccess: settle,
    }),
    feature: useMutation({
      mutationFn: ({ id, on }: { id: string; on: boolean }) =>
        unwrap(api.PUT("/api/v1/admin/sellers/{seller_id}/featured", { ...path(id), body: { on } })),
      onSuccess: settle,
    }),
  };
}

// ─── Users ─────────────────────────────────────────────────────────────────

export interface UserFilters {
  q: string;
  role: "BUYER" | "SELLER" | "ADMIN" | null;
  status: "active" | "banned" | null;
  offset: number;
}

export const USERS_PAGE = 20;

export function useAdminUsers(f: UserFilters) {
  const on = useAdmin();
  return useQuery({
    queryKey: [...K.users, f],
    enabled: on,
    placeholderData: (prev) => prev,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/users", {
          params: {
            query: {
              ...(f.q.trim() ? { q: f.q.trim() } : {}),
              ...(f.role ? { role: f.role } : {}),
              ...(f.status ? { status: f.status } : {}),
              limit: USERS_PAGE,
              offset: f.offset,
            },
          },
        }),
      ),
  });
}

export function useAdminUser(id: string | null) {
  const on = useAdmin();
  return useQuery({
    queryKey: [...K.users, "detail", id],
    enabled: on && !!id,
    queryFn: () => unwrap(api.GET("/api/v1/admin/users/{user_id}", { params: { path: { user_id: id! } } })),
  });
}

export function useUserActions() {
  const qc = useQueryClient();
  const settle = () => {
    qc.invalidateQueries({ queryKey: K.users });
    qc.invalidateQueries({ queryKey: K.audit });
  };
  return {
    setStatus: useMutation({
      mutationFn: ({ id, status, reason }: { id: string; status: "active" | "banned"; reason: string }) =>
        unwrap(api.PATCH("/api/v1/admin/users/{user_id}/status", { params: { path: { user_id: id } }, body: { status, reason } })),
      onSuccess: settle,
    }),
    setRoles: useMutation({
      mutationFn: ({ id, roles, reason }: { id: string; roles: ("BUYER" | "SELLER")[]; reason: string }) =>
        unwrap(api.PATCH("/api/v1/admin/users/{user_id}/roles", { params: { path: { user_id: id } }, body: { roles, reason } })),
      onSuccess: settle,
    }),
  };
}

// ─── Catalog ───────────────────────────────────────────────────────────────

export function useAdminCategories() {
  const on = useAdmin();
  return useQuery({
    queryKey: [...K.catalog, "categories"],
    enabled: on,
    queryFn: () => unwrap(api.GET("/api/v1/admin/catalog/categories")),
  });
}

export function usePicks(subId: string | null) {
  const on = useAdmin();
  return useQuery({
    queryKey: [...K.catalog, "picks", subId],
    enabled: on && !!subId,
    queryFn: () =>
      unwrap(api.GET("/api/v1/admin/catalog/subcategories/{sub_id}/picks", { params: { path: { sub_id: subId! } } })),
  });
}

export function useAdminCollections() {
  const on = useAdmin();
  return useQuery({
    queryKey: [...K.catalog, "collections"],
    enabled: on,
    queryFn: () => unwrap(api.GET("/api/v1/admin/catalog/collections")),
  });
}

export function useCatalogActions() {
  const qc = useQueryClient();
  const settle = () => {
    qc.invalidateQueries({ queryKey: K.catalog });
    qc.invalidateQueries({ queryKey: K.audit });
  };
  return {
    updateCategory: useMutation({
      mutationFn: ({ id, body }: { id: string; body: ApiSchemas["CategoryPatch"] }) =>
        unwrap(api.PATCH("/api/v1/admin/catalog/categories/{category_id}", { params: { path: { category_id: id } }, body })),
      onSuccess: settle,
    }),
    addSub: useMutation({
      mutationFn: ({ categoryId, name }: { categoryId: string; name: string }) =>
        unwrap(api.POST("/api/v1/admin/catalog/categories/{category_id}/subcategories", { params: { path: { category_id: categoryId } }, body: { name } })),
      onSuccess: settle,
    }),
    updateSub: useMutation({
      mutationFn: ({ id, body }: { id: string; body: ApiSchemas["SubcategoryPatch"] }) =>
        unwrap(api.PATCH("/api/v1/admin/catalog/subcategories/{sub_id}", { params: { path: { sub_id: id } }, body })),
      onSuccess: settle,
    }),
    deleteSub: useMutation({
      mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/admin/catalog/subcategories/{sub_id}", { params: { path: { sub_id: id } } })),
      onSuccess: settle,
    }),
    setPick: useMutation({
      mutationFn: ({ productId, on }: { productId: string; on: boolean }) =>
        unwrap(api.PUT("/api/v1/admin/catalog/products/{product_id}/pick", { params: { path: { product_id: productId } }, body: { on } })),
      onSuccess: settle,
    }),
    saveCollection: useMutation({
      mutationFn: ({ id, body }: { id?: string; body: ApiSchemas["CollectionIn"] }) =>
        id
          ? unwrap(api.PUT("/api/v1/admin/catalog/collections/{collection_id}", { params: { path: { collection_id: id } }, body }))
          : unwrap(api.POST("/api/v1/admin/catalog/collections", { body })),
      onSuccess: settle,
    }),
    deleteCollection: useMutation({
      mutationFn: (id: string) =>
        unwrap(api.DELETE("/api/v1/admin/catalog/collections/{collection_id}", { params: { path: { collection_id: id } } })),
      onSuccess: settle,
    }),
  };
}

// ─── Moderation ────────────────────────────────────────────────────────────

export function useModeration(status: "open" | "resolved") {
  const on = useAdmin();
  return useQuery({
    queryKey: [...K.moderation, status],
    enabled: on,
    queryFn: () => unwrap(api.GET("/api/v1/admin/moderation", { params: { query: { status } } })),
  });
}

export function useModerate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { type: "product" | "review"; id: string; action: ApiSchemas["ModerationAction"]["action"]; note?: string }) =>
      unwrap(
        api.POST("/api/v1/admin/moderation/{target_type}/{target_id}", {
          params: { path: { target_type: v.type, target_id: v.id } },
          body: { action: v.action, note: v.note || null },
        }),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: K.moderation });
      qc.invalidateQueries({ queryKey: K.overview });
      qc.invalidateQueries({ queryKey: K.audit });
    },
  });
}

// ─── QueWallet (platform) ──────────────────────────────────────────────────

export function useSystemWallets() {
  const on = useAdmin();
  return useQuery({ queryKey: [...K.wallet, "system"], enabled: on, queryFn: () => unwrap(api.GET("/api/v1/admin/wallet/system")) });
}

export function useCodes() {
  const on = useAdmin();
  return useQuery({ queryKey: [...K.wallet, "codes"], enabled: on, queryFn: () => unwrap(api.GET("/api/v1/admin/wallet/codes")) });
}

export function useLedger(type: string | null) {
  const on = useAdmin();
  return useInfiniteQuery({
    queryKey: [...K.wallet, "ledger", type],
    enabled: on,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/admin/wallet/transactions", {
          params: { query: { limit: 20, ...(type ? { type } : {}), ...(pageParam ? { cursor: pageParam } : {}) } },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor,
  });
}

export function useWalletActions() {
  const qc = useQueryClient();
  const settle = () => {
    qc.invalidateQueries({ queryKey: K.wallet });
    qc.invalidateQueries({ queryKey: K.overview });
    qc.invalidateQueries({ queryKey: K.audit });
  };
  return {
    reconcile: useMutation({ mutationFn: () => unwrap(api.GET("/api/v1/admin/wallet/reconcile")) }),
    grant: useMutation({
      mutationFn: ({ body, key }: { body: ApiSchemas["GrantRequest"]; key: string }) =>
        unwrap(api.POST("/api/v1/admin/wallet/grants", { body, params: { header: { "Idempotency-Key": key } } })),
      onSuccess: settle,
    }),
    createCode: useMutation({
      mutationFn: (body: ApiSchemas["CodeCreate"]) => unwrap(api.POST("/api/v1/admin/wallet/codes", { body })),
      onSuccess: settle,
    }),
    reverse: useMutation({
      mutationFn: ({ id, reason }: { id: string; reason: string }) =>
        unwrap(api.POST("/api/v1/admin/wallet/transactions/{tx_id}/reverse", { params: { path: { tx_id: id } }, body: { reason } })),
      onSuccess: settle,
    }),
    fastForward: useMutation({
      mutationFn: () => unwrap(api.POST("/api/v1/admin/orders/release-due", { params: { query: { fast_forward: true } } })),
      onSuccess: settle,
    }),
  };
}

// ─── Audit ─────────────────────────────────────────────────────────────────

export function useAudit(f: { action: string; targetType: string }) {
  const on = useAdmin();
  return useInfiniteQuery({
    queryKey: [...K.audit, f],
    enabled: on,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/admin/audit", {
          params: {
            query: {
              limit: 30,
              ...(f.action.trim() ? { action: f.action.trim() } : {}),
              ...(f.targetType ? { target_type: f.targetType } : {}),
              ...(pageParam ? { cursor: pageParam } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor,
  });
}

// ─── Promotions (platform sales) ───────────────────────────────────────────

export function useAdminPromotions() {
  const on = useAdmin();
  return useQuery({ queryKey: K.promotions, enabled: on, queryFn: () => unwrap(api.GET("/api/v1/admin/promotions")) });
}

export function usePromotionActions() {
  const qc = useQueryClient();
  const settle = () => qc.invalidateQueries({ queryKey: K.promotions });
  const save = useMutation({
    mutationFn: ({ id, body }: { id?: string; body: PromotionIn }) =>
      unwrap(
        id
          ? api.PUT("/api/v1/admin/promotions/{promotion_id}", { params: { path: { promotion_id: id } }, body })
          : api.POST("/api/v1/admin/promotions", { body }),
      ),
    onSuccess: settle,
  });
  const cancel = useMutation({
    mutationFn: (id: string) =>
      unwrap(api.POST("/api/v1/admin/promotions/{promotion_id}/cancel", { params: { path: { promotion_id: id } } })),
    onSuccess: settle,
  });
  return { save, cancel };
}
