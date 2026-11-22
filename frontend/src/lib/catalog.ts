import "server-only";

import { notFound } from "next/navigation";

import { createServerApi, type ApiSchemas } from "@/lib/api/client";

export type ProductCardData = ApiSchemas["ProductCard"];
export type ProductDetail = ApiSchemas["ProductDetail"];
export type Listing = ApiSchemas["ProductListing"];
export type HomeData = ApiSchemas["HomeOut"];
export type Category = ApiSchemas["CategoryOut"];
export type Boutique = ApiSchemas["BoutiqueDetail"];
export type BoutiqueCard = ApiSchemas["BoutiqueCard"];
export type Collection = ApiSchemas["CollectionOut"];
export type Drop = ApiSchemas["DropOut"];

/** Thrown into the nearest error.tsx when the API is down (not a 404). */
export class CatalogUnavailable extends Error {}

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.response.status === 404) notFound();
  if (result.error || result.data === undefined) {
    throw new CatalogUnavailable(`Catalog request failed (${result.response.status})`);
  }
  return result.data;
}

export async function getHome() {
  return unwrap(await createServerApi().GET("/api/v1/catalog/home"));
}

export async function getCategories() {
  return unwrap(await createServerApi().GET("/api/v1/catalog/categories"));
}

export async function getCategory(slug: string) {
  return unwrap(
    await createServerApi().GET("/api/v1/catalog/categories/{slug}", { params: { path: { slug } } }),
  );
}

export async function getProduct(slug: string) {
  return unwrap(
    await createServerApi().GET("/api/v1/catalog/products/{slug}", { params: { path: { slug } } }),
  );
}

export async function getBoutiques() {
  return unwrap(await createServerApi().GET("/api/v1/catalog/boutiques"));
}

export async function getBoutique(slug: string) {
  return unwrap(
    await createServerApi().GET("/api/v1/catalog/boutiques/{slug}", { params: { path: { slug } } }),
  );
}

export async function getCollections() {
  return unwrap(await createServerApi().GET("/api/v1/catalog/collections"));
}

export async function getCollection(slug: string) {
  return unwrap(
    await createServerApi().GET("/api/v1/catalog/collections/{slug}", { params: { path: { slug } } }),
  );
}

export async function getDrops() {
  return unwrap(await createServerApi().GET("/api/v1/catalog/drops"));
}

export type ListingQuery = NonNullable<
  NonNullable<Parameters<ReturnType<typeof createServerApi>["GET"]>[1]>["params"]
>["query"];

export async function getListing(query: Record<string, string | string[] | undefined>) {
  const res = await createServerApi().GET("/api/v1/catalog/products", {
    params: { query: query as never },
  });
  if (res.response.status === 422) {
    return { listing: null, corrected: null };
  }
  return {
    listing: unwrap(res),
    corrected: res.response.headers.get("X-Search-Corrected"),
  };
}
