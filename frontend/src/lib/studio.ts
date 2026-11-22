"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type ApiSchemas } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";

export type Application = ApiSchemas["SellerApplicationOut"];
export type ApplicationIn = ApiSchemas["SellerApplicationIn"];
export type BoutiqueSettings = ApiSchemas["BoutiqueSettingsOut"];
export type StudioProduct = ApiSchemas["StudioProduct"];
export type StudioProductRow = ApiSchemas["StudioProductRow"];
export type ProductPatch = ApiSchemas["ProductPatch"];
export type StudioMeta = ApiSchemas["StudioMeta"];
export type InventoryRow = ApiSchemas["InventoryRow"];
export type Dashboard = ApiSchemas["Dashboard"];
export type Earnings = ApiSchemas["Earnings"];
export type StudioDrop = ApiSchemas["StudioDrop"];
export type DropIn = ApiSchemas["DropIn"];
export type StudioVoucher = ApiSchemas["StudioVoucher"];
export type VoucherIn = ApiSchemas["VoucherIn"];
export type StudioReview = ApiSchemas["StudioReview"];

const K = {
  app: ["seller-application"] as const,
  dash: ["studio", "dashboard"] as const,
  settings: ["studio", "settings"] as const,
  earnings: ["studio", "earnings"] as const,
  meta: ["studio", "meta"] as const,
  products: ["studio", "products"] as const,
  product: (id: string) => ["studio", "products", id] as const,
  inventory: ["studio", "inventory"] as const,
  drops: ["studio", "drops"] as const,
  vouchers: ["studio", "vouchers"] as const,
  reviews: ["studio", "reviews"] as const,
};

/** openapi-fetch results → data or throw the API error envelope. */
async function unwrap<T>(p: Promise<{ data?: T; error?: unknown }>): Promise<T> {
  const { data, error } = await p;
  if (error !== undefined) throw error;
  return data as T;
}

function useAuthed() {
  const { status } = useSession();
  return status === "authenticated";
}

// ─── Application ───────────────────────────────────────────────────────────

export function useApplication() {
  const on = useAuthed();
  return useQuery({ queryKey: K.app, enabled: on, queryFn: () => unwrap(api.GET("/api/v1/seller-application")) });
}

export function useApply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApplicationIn) => unwrap(api.PUT("/api/v1/seller-application", { body })),
    onSuccess: (data) => qc.setQueryData(K.app, data),
  });
}

// ─── Dashboard, settings, earnings ─────────────────────────────────────────

export function useDashboard() {
  const on = useAuthed();
  return useQuery({ queryKey: K.dash, enabled: on, queryFn: () => unwrap(api.GET("/api/v1/seller/dashboard")) });
}

export function useDismissFirstSale() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/seller/first-sale/dismiss")),
    onSuccess: () => qc.setQueryData<Dashboard>(K.dash, (d) => (d ? { ...d, first_sale: false } : d)),
  });
}

export function useBoutiqueSettings() {
  const on = useAuthed();
  return useQuery({ queryKey: K.settings, enabled: on, queryFn: () => unwrap(api.GET("/api/v1/seller/settings")) });
}

export function useSaveSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApiSchemas["BoutiqueSettingsIn"]) => unwrap(api.PUT("/api/v1/seller/settings", { body })),
    onSuccess: (data) => qc.setQueryData(K.settings, data),
  });
}

export function useEarnings() {
  const on = useAuthed();
  return useQuery({ queryKey: K.earnings, enabled: on, queryFn: () => unwrap(api.GET("/api/v1/seller/earnings")) });
}

// ─── Products ──────────────────────────────────────────────────────────────

export function useStudioMeta() {
  const on = useAuthed();
  return useQuery({
    queryKey: K.meta,
    enabled: on,
    staleTime: 10 * 60_000,
    queryFn: () => unwrap(api.GET("/api/v1/seller/products/meta")),
  });
}

export function useStudioProducts(status: "draft" | "active" | "archived" | null, q: string) {
  const on = useAuthed();
  return useQuery({
    queryKey: [...K.products, "list", status, q],
    enabled: on,
    placeholderData: (prev) => prev,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/seller/products", {
          params: { query: { ...(status ? { status } : {}), ...(q.trim() ? { q: q.trim() } : {}) } },
        }),
      ),
  });
}

export function useStudioProduct(id: string | null) {
  const on = useAuthed();
  return useQuery({
    queryKey: K.product(id ?? "new"),
    enabled: on && !!id,
    queryFn: () => unwrap(api.GET("/api/v1/seller/products/{product_id}", { params: { path: { product_id: id! } } })),
  });
}

export function useProductActions() {
  const qc = useQueryClient();
  const settle = (p?: StudioProduct) => {
    if (p) qc.setQueryData(K.product(p.id), p);
    qc.invalidateQueries({ queryKey: [...K.products, "list"] });
    qc.invalidateQueries({ queryKey: K.inventory });
    qc.invalidateQueries({ queryKey: K.dash });
  };
  const create = useMutation({
    mutationFn: (body: ApiSchemas["ProductBasics"]) => unwrap(api.POST("/api/v1/seller/products", { body })),
    onSuccess: settle,
  });
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: ProductPatch }) =>
      unwrap(api.PATCH("/api/v1/seller/products/{product_id}", { params: { path: { product_id: id } }, body })),
    onSuccess: settle,
  });
  const publish = useMutation({
    mutationFn: (id: string) =>
      unwrap(api.POST("/api/v1/seller/products/{product_id}/publish", { params: { path: { product_id: id } } })),
    onSuccess: settle,
  });
  const duplicate = useMutation({
    mutationFn: (id: string) =>
      unwrap(api.POST("/api/v1/seller/products/{product_id}/duplicate", { params: { path: { product_id: id } } })),
    onSuccess: settle,
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      unwrap(api.DELETE("/api/v1/seller/products/{product_id}", { params: { path: { product_id: id } } })),
    onSuccess: () => settle(),
  });
  const archive = useMutation({
    mutationFn: ({ ids, restore }: { ids: string[]; restore?: boolean }) =>
      unwrap(api.POST(restore ? "/api/v1/seller/products/restore" : "/api/v1/seller/products/archive", { body: { ids } })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: K.products });
      settle();
    },
  });
  return { create, patch, publish, duplicate, remove, archive };
}

// ─── Inventory ─────────────────────────────────────────────────────────────

export function useInventory(low: boolean) {
  const on = useAuthed();
  return useQuery({
    queryKey: [...K.inventory, low],
    enabled: on,
    queryFn: () => unwrap(api.GET("/api/v1/seller/inventory", { params: { query: { low } } })),
  });
}

export function useUpdateInventory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (updates: ApiSchemas["InventoryUpdate"][]) =>
      unwrap(api.PATCH("/api/v1/seller/inventory", { body: { updates } })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: K.inventory });
      qc.invalidateQueries({ queryKey: K.products });
      qc.invalidateQueries({ queryKey: K.dash });
    },
  });
}

// ─── Drops ─────────────────────────────────────────────────────────────────

export function useStudioDrops() {
  const on = useAuthed();
  return useQuery({ queryKey: K.drops, enabled: on, queryFn: () => unwrap(api.GET("/api/v1/seller/drops")) });
}

export function useDropActions() {
  const qc = useQueryClient();
  const settle = () => {
    qc.invalidateQueries({ queryKey: K.drops });
    qc.invalidateQueries({ queryKey: K.products });
  };
  const save = useMutation({
    mutationFn: ({ id, body }: { id?: string; body: DropIn }) =>
      id
        ? unwrap(api.PUT("/api/v1/seller/drops/{drop_id}", { params: { path: { drop_id: id } }, body }))
        : unwrap(api.POST("/api/v1/seller/drops", { body })),
    onSuccess: settle,
  });
  const remove = useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/seller/drops/{drop_id}", { params: { path: { drop_id: id } } })),
    onSuccess: settle,
  });
  return { save, remove };
}

// ─── Vouchers ──────────────────────────────────────────────────────────────

export function useStudioVouchers() {
  const on = useAuthed();
  return useQuery({ queryKey: K.vouchers, enabled: on, queryFn: () => unwrap(api.GET("/api/v1/seller/vouchers")) });
}

export function useVoucherActions() {
  const qc = useQueryClient();
  const settle = () => qc.invalidateQueries({ queryKey: K.vouchers });
  const create = useMutation({
    mutationFn: (body: VoucherIn) => unwrap(api.POST("/api/v1/seller/vouchers", { body })),
    onSuccess: settle,
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: ApiSchemas["VoucherPatch"] }) =>
      unwrap(api.PATCH("/api/v1/seller/vouchers/{voucher_id}", { params: { path: { voucher_id: id } }, body })),
    onSuccess: settle,
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      unwrap(api.DELETE("/api/v1/seller/vouchers/{voucher_id}", { params: { path: { voucher_id: id } } })),
    onSuccess: settle,
  });
  return { create, update, remove };
}

// ─── Reviews ───────────────────────────────────────────────────────────────

export function useStudioReviews(unreplied: boolean) {
  const on = useAuthed();
  return useQuery({
    queryKey: [...K.reviews, unreplied],
    enabled: on,
    queryFn: () => unwrap(api.GET("/api/v1/seller/reviews", { params: { query: { unreplied } } })),
  });
}

export function useReply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reply }: { id: string; reply: string }) =>
      unwrap(api.PUT("/api/v1/seller/reviews/{review_id}/reply", { params: { path: { review_id: id } }, body: { reply } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: K.reviews }),
  });
}
