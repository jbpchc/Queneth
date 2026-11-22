"use client";

import { MapPin } from "lucide-react";
import { useState, type FormEvent } from "react";

import { AddressPicker, emptyPlace, type AddressPlace } from "@/components/forms/address-picker";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/states";
import { fieldErrors, toApiError } from "@/lib/api/client";
import { addressLine, formatPhone, useAddressMutations, type Address } from "@/lib/commerce";

type Errors = Partial<Record<"label" | "recipient" | "phone" | "line1" | "zip" | "barangay", string>>;

/**
 * Add or edit a shipping address. Places come from the PSGC lists (no free
 * typing); the server resolves and stores the official names.
 * UX: Postel's Law — "0917 123 4567", "+63 917…" and "9171234567" all work.
 * UX: Cognitive Load — label chips (Home, Office) instead of a blank field.
 */
export function AddressForm({
  address,
  defaultName,
  onSaved,
  onCancel,
  submitLabel = "Save address",
}: {
  address?: Address;
  defaultName?: string;
  onSaved: (a: Address) => void;
  onCancel?: () => void;
  submitLabel?: string;
}) {
  const { save } = useAddressMutations();
  const [label, setLabel] = useState(address?.label ?? "Home");
  const [recipient, setRecipient] = useState(address?.recipient ?? defaultName ?? "");
  const [phone, setPhone] = useState(address ? formatPhone(address.phone) : "");
  const [line1, setLine1] = useState(address?.line1 ?? "");
  const [zip, setZip] = useState(address?.zip ?? "");
  const [isDefault, setIsDefault] = useState(address?.is_default ?? false);
  // Editing keeps the saved place until the buyer chooses to change it.
  const [changingPlace, setChangingPlace] = useState(!address);
  const [place, setPlace] = useState<AddressPlace>(emptyPlace);
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const barangayCode = changingPlace ? place.barangay?.code : address?.barangay_code;
    const next: Errors = {};
    if (!recipient.trim()) next.recipient = "Who should receive the parcel?";
    if (!phone.trim()) next.phone = "Add a mobile number for the courier.";
    if (line1.trim().length < 3) next.line1 = "Add the house number and street.";
    if (!/^\d{4}$/.test(zip.trim())) next.zip = "ZIP codes have 4 digits.";
    if (!barangayCode) next.barangay = "Choose down to the barangay.";
    setErrors(next);
    setFormError(null);
    if (Object.keys(next).length) return;
    try {
      const saved = await save.mutateAsync({
        id: address?.id,
        body: {
          label: label.trim() || "Home",
          recipient,
          phone,
          line1,
          zip: zip.trim(),
          barangay_code: barangayCode!,
          is_default: isDefault,
        },
      });
      onSaved(saved);
    } catch (err) {
      const api = toApiError(err);
      const fields = fieldErrors(api);
      if (Object.keys(fields).length) setErrors({ ...fields, barangay: fields.barangay_code });
      else setFormError(api.message);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      {formError && <Alert tone="danger">{formError}</Alert>}
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-small font-semibold text-ink">Label</legend>
        <div className="flex flex-wrap gap-2">
          {["Home", "Office", "Studio"].map((l) => (
            <button
              key={l}
              type="button"
              aria-pressed={label === l}
              onClick={() => setLabel(l)}
              className="h-11 rounded-pill border border-border-strong px-4 text-small font-semibold aria-pressed:border-ink aria-pressed:bg-ink aria-pressed:text-bg"
            >
              {l}
            </button>
          ))}
          <Input
            aria-label="Custom label"
            placeholder="Other…"
            value={["Home", "Office", "Studio"].includes(label) ? "" : label}
            onChange={(e) => setLabel(e.target.value.slice(0, 40))}
            className="h-11 w-36"
          />
        </div>
      </fieldset>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Recipient" error={errors.recipient}>
          <Input value={recipient} onChange={(e) => setRecipient(e.target.value)} autoComplete="name" />
        </Field>
        <Field label="Mobile number" hint="For the courier, e.g. 0917 123 4567" error={errors.phone}>
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" />
        </Field>
      </div>
      {changingPlace ? (
        <AddressPicker value={place} onChange={setPlace} errors={{ barangay: errors.barangay }} />
      ) : (
        <div className="flex flex-wrap items-center gap-3 rounded-input bg-surface-muted p-4">
          <MapPin aria-hidden className="size-4 text-ink-muted" />
          <p className="flex-1 text-small text-ink">
            {addressLine({ barangay: address?.barangay, city: address?.city, province: address?.province ?? address?.region })}
          </p>
          <Button type="button" variant="outline" size="sm" onClick={() => setChangingPlace(true)}>
            Change area
          </Button>
        </div>
      )}
      <div className="grid gap-5 sm:grid-cols-[1fr_140px]">
        <Field label="House no., street, building" error={errors.line1}>
          <Input value={line1} onChange={(e) => setLine1(e.target.value)} autoComplete="address-line1" />
        </Field>
        <Field label="ZIP code" error={errors.zip}>
          <Input value={zip} onChange={(e) => setZip(e.target.value.replace(/\D/g, "").slice(0, 4))} inputMode="numeric" autoComplete="postal-code" />
        </Field>
      </div>
      <label className="flex min-h-11 items-center gap-3 text-small text-ink">
        <Checkbox checked={isDefault} onCheckedChange={(v) => setIsDefault(v === true)} />
        Use as my default address
      </label>
      <div className="flex flex-wrap justify-end gap-3">
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" variant="primary" loading={save.isPending}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
