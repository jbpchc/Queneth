"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiSchemas } from "@/lib/api/client";

export type GeoArea = ApiSchemas["GeoArea"];
export type GeoList = ApiSchemas["GeoList"];

// Geography barely changes: cache for the whole session.
const geoQuery = { staleTime: Infinity, gcTime: 60 * 60 * 1000, retry: 1 } as const;

async function unwrap(p: Promise<{ data?: GeoList; error?: unknown }>): Promise<GeoList> {
  const { data, error } = await p;
  if (error || !data) throw error ?? new Error("No data");
  return data;
}

export function useRegions() {
  return useQuery({
    ...geoQuery,
    queryKey: ["geo", "regions"],
    queryFn: () => unwrap(api.GET("/api/v1/geo/regions")),
  });
}

export function useProvinces(regionCode: string | null) {
  return useQuery({
    ...geoQuery,
    queryKey: ["geo", "provinces", regionCode],
    enabled: !!regionCode,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/geo/regions/{region_code}/provinces", {
          params: { path: { region_code: regionCode! } },
        }),
      ),
  });
}

/** Cities of a province, or the province-less cities of a region (NCR / independent). */
export function useCities(regionCode: string | null, provinceCode: string | null, enabled: boolean) {
  return useQuery({
    ...geoQuery,
    queryKey: ["geo", "cities", regionCode, provinceCode],
    enabled: !!regionCode && enabled,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/geo/regions/{region_code}/cities", {
          params: {
            path: { region_code: regionCode! },
            query: provinceCode ? { province: provinceCode } : {},
          },
        }),
      ),
  });
}

export function useBarangays(cityCode: string | null) {
  return useQuery({
    ...geoQuery,
    queryKey: ["geo", "barangays", cityCode],
    enabled: !!cityCode,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/geo/cities/{city_code}/barangays", {
          params: { path: { city_code: cityCode! } },
        }),
      ),
  });
}
