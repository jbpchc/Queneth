"use client";

import { Info } from "lucide-react";
import type { ReactNode } from "react";

import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { toApiError } from "@/lib/api/client";
import { useBarangays, useCities, useProvinces, useRegions, type GeoArea } from "@/lib/geo";
import { cn } from "@/lib/utils";

export interface AddressPlace {
  region: GeoArea | null;
  province: GeoArea | null;
  city: GeoArea | null;
  barangay: GeoArea | null;
}

export const emptyPlace: AddressPlace = { region: null, province: null, city: null, barangay: null };

interface AddressPickerProps {
  value: AddressPlace;
  onChange: (value: AddressPlace) => void;
  errors?: Partial<Record<keyof AddressPlace, string>>;
  disabled?: boolean;
  className?: string;
}

/**
 * Cascading Region → Province → City/Municipality → Barangay dropdowns backed by
 * the PSGC API (proxied, cached, with an offline snapshot fallback).
 *
 * UX: Tesler's Law — the official lists absorb the complexity; no free-typed
 * place names to misspell. UX: Jakob's Law — native selects keep the phone's
 * own picker and type-to-search. NCR has no provinces, so that step is skipped.
 */
export function AddressPicker({ value, onChange, errors, disabled, className }: AddressPickerProps) {
  const regions = useRegions();
  const provinces = useProvinces(value.region?.code ?? null);
  const noProvinces = provinces.isSuccess && provinces.data.items.length === 0;
  const cities = useCities(
    value.region?.code ?? null,
    value.province?.code ?? null,
    noProvinces || !!value.province,
  );
  const barangays = useBarangays(value.city?.code ?? null);

  const pick = (list: GeoArea[] | undefined, code: string) => list?.find((a) => a.code === code) ?? null;

  return (
    <div className={cn("grid gap-5 sm:grid-cols-2", className)}>
      <Level
        label="Region"
        state={regions}
        value={value.region?.code}
        placeholder="Choose a region"
        error={errors?.region}
        disabled={disabled}
        onSelect={(code) => onChange({ ...emptyPlace, region: pick(regions.data?.items, code) })}
      />
      {noProvinces ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-small font-semibold text-ink">Province</span>
          <p className="flex min-h-12 items-center gap-2 rounded-input bg-surface-muted px-3.5 text-small text-ink-muted">
            <Info aria-hidden className="size-4 shrink-0" />
            Metro Manila has no provinces. Pick your city next.
          </p>
        </div>
      ) : (
        <Level
          label="Province"
          state={provinces}
          enabled={!!value.region}
          value={value.province?.code}
          placeholder={value.region ? "Choose a province" : "Choose a region first"}
          error={errors?.province}
          disabled={disabled}
          onSelect={(code) =>
            onChange({ ...value, province: pick(provinces.data?.items, code), city: null, barangay: null })
          }
        />
      )}
      <Level
        label="City / municipality"
        state={cities}
        enabled={!!value.region && (noProvinces || !!value.province)}
        value={value.city?.code}
        placeholder={value.province || noProvinces ? "Choose a city or municipality" : "Choose a province first"}
        error={errors?.city}
        disabled={disabled}
        onSelect={(code) => onChange({ ...value, city: pick(cities.data?.items, code), barangay: null })}
      />
      <Level
        label="Barangay"
        state={barangays}
        enabled={!!value.city}
        value={value.barangay?.code}
        placeholder={value.city ? "Choose a barangay" : "Choose a city first"}
        error={errors?.barangay}
        disabled={disabled}
        onSelect={(code) => onChange({ ...value, barangay: pick(barangays.data?.items, code) })}
      />
    </div>
  );
}

interface LevelProps {
  label: string;
  state: {
    data?: { items: GeoArea[] };
    isLoading: boolean;
    isError: boolean;
    error: unknown;
    refetch: () => unknown;
  };
  enabled?: boolean;
  value: string | undefined;
  placeholder: string;
  error?: string;
  disabled?: boolean;
  onSelect: (code: string) => void;
}

function Level({ label, state, enabled = true, value, placeholder, error, disabled, onSelect }: LevelProps) {
  let hint: ReactNode;
  if (state.isError) {
    hint = (
      <span className="text-danger">
        {toApiError(state.error).message}{" "}
        <button type="button" onClick={() => state.refetch()} className="font-semibold underline">
          Retry
        </button>
      </span>
    );
  }
  return (
    <Field label={label} error={error} hint={hint}>
      <Select
        value={value ?? ""}
        disabled={disabled || !enabled || state.isLoading || state.isError}
        aria-busy={state.isLoading || undefined}
        onChange={(e) => onSelect(e.target.value)}
      >
        <option value="" disabled>
          {state.isLoading ? "Loading…" : placeholder}
        </option>
        {state.data?.items.map((a) => (
          <option key={a.code} value={a.code}>
            {a.name}
          </option>
        ))}
      </Select>
    </Field>
  );
}
