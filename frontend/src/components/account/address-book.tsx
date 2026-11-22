"use client";

import { MapPin, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toApiError } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { addressLine, formatPhone, useAddresses, useAddressMutations, type Address } from "@/lib/commerce";

import { AddressForm } from "./address-form";

/** Saved addresses: default first, edit / make default / delete. */
export function AddressBook() {
  const { user } = useSession();
  const addresses = useAddresses();
  const { makeDefault, remove } = useAddressMutations();
  const [editing, setEditing] = useState<Address | "new" | null>(null);

  if (addresses.isPending) {
    return (
      <div className="grid gap-4 sm:grid-cols-2" aria-busy="true" aria-label="Loading addresses">
        <Skeleton className="h-40 rounded-card" />
        <Skeleton className="h-40 rounded-card" />
      </div>
    );
  }
  if (addresses.isError) {
    return <ErrorState message={toApiError(addresses.error).message} onRetry={() => addresses.refetch()} />;
  }

  const rows = addresses.data;
  return (
    <>
      {rows.length === 0 ? (
        <EmptyState
          icon={MapPin}
          title="No saved addresses yet"
          description="Save one now and checkout takes a single tap."
          action={<Button variant="primary" onClick={() => setEditing("new")}><Plus aria-hidden /> Add an address</Button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {rows.map((a) => (
            // UX: Common Region — each address is one bounded card.
            <Card key={a.id} className="flex flex-col gap-3 p-5">
              <div className="flex items-center gap-2">
                <p className="font-semibold text-ink">{a.label}</p>
                {a.is_default && <Badge tone="info" withIcon={false}>Default</Badge>}
              </div>
              <div className="flex flex-col gap-0.5 text-small">
                <p className="text-ink">{a.recipient} · <span className="tabular">{formatPhone(a.phone)}</span></p>
                <p className="text-ink-muted">{addressLine(a)}</p>
              </div>
              <div className="mt-auto flex flex-wrap gap-2 pt-2">
                <Button variant="outline" size="sm" onClick={() => setEditing(a)}><Pencil aria-hidden /> Edit</Button>
                {!a.is_default && (
                  <Button variant="ghost" size="sm" loading={makeDefault.isPending && makeDefault.variables === a.id} onClick={() => makeDefault.mutate(a.id)}>
                    Make default
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-auto text-ink-muted hover:text-danger"
                  aria-label={`Delete ${a.label} address`}
                  onClick={() => remove.mutate(a.id, { onSuccess: () => toast.success(`${a.label} address deleted`) })}
                >
                  <Trash2 aria-hidden />
                </Button>
              </div>
            </Card>
          ))}
          <button
            type="button"
            onClick={() => setEditing("new")}
            className="flex min-h-40 flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed border-border-strong text-small font-semibold text-ink-muted hover:border-ink hover:text-ink"
          >
            <Plus aria-hidden className="size-5" /> Add an address
          </button>
        </div>
      )}

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing === "new" ? "New address" : "Edit address"}</DialogTitle>
            <DialogDescription>We ship anywhere in the Philippines. Pick your area from the official lists.</DialogDescription>
          </DialogHeader>
          {editing !== null && (
            <AddressForm
              key={editing === "new" ? "new" : editing.id}
              address={editing === "new" ? undefined : editing}
              defaultName={user?.name}
              onCancel={() => setEditing(null)}
              onSaved={(a) => {
                setEditing(null);
                toast.success(`${a.label} address saved`);
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
