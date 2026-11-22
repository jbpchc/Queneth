"use client";

import { ExternalLink } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { SingleImageField, SortableImages, type GalleryItem } from "@/components/studio/uploads";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, ErrorState } from "@/components/ui/states";
import { fieldErrors, toApiError } from "@/lib/api/client";
import { formatQc } from "@/lib/format";
import { useBoutiqueSettings, useSaveSettings, useStudioProducts, type BoutiqueSettings } from "@/lib/studio";
import { cn } from "@/lib/utils";

export function SettingsView() {
  const settings = useBoutiqueSettings();
  if (settings.isPending) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading settings">
        <Skeleton className="h-10 w-60" />
        <Skeleton className="h-96 rounded-card" />
      </div>
    );
  }
  if (settings.isError) return <ErrorState message={toApiError(settings.error).message} onRetry={() => settings.refetch()} />;
  return <SettingsForm s={settings.data} />;
}

/**
 * Storefront settings: identity, policies, up to 4 featured pieces and a
 * 6-image lookbook. UX: Chunking — four short sections, one save.
 */
function SettingsForm({ s }: { s: BoutiqueSettings }) {
  const save = useSaveSettings();
  const products = useStudioProducts("active", "");
  const [tagline, setTagline] = useState(s.tagline ?? "");
  const [bio, setBio] = useState(s.bio ?? "");
  const [policy, setPolicy] = useState(s.return_policy ?? "");
  const [email, setEmail] = useState(s.contact_email ?? "");
  const [city, setCity] = useState(s.city ?? "");
  const [logo, setLogo] = useState<GalleryItem | null>(null);
  const [banner, setBanner] = useState<GalleryItem | null>(null);
  const [featured, setFeatured] = useState<string[]>(s.featured_product_ids);
  const [look, setLook] = useState<GalleryItem[]>(s.lookbook.map((l, i) => ({ key: `${i}-${l.url}`, url: l.url, text: l.caption ?? "" })));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const toggle = (id: string) =>
    setFeatured((f) => (f.includes(id) ? f.filter((x) => x !== id) : f.length >= 4 ? f : [...f, id]));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErrors({});
    setFormError(null);
    try {
      await save.mutateAsync({
        tagline: tagline || null,
        bio,
        return_policy: policy,
        contact_email: email,
        city,
        logo_asset_id: logo?.assetId ?? null,
        banner_asset_id: banner?.assetId ?? null,
        featured_product_ids: featured,
        lookbook: look.map((l) => (l.assetId ? { asset_id: l.assetId, caption: l.text || null } : { url: l.url, caption: l.text || null })),
      });
      setLogo(null);
      setBanner(null);
      toast.success("Storefront saved");
    } catch (err) {
      const api = toApiError(err);
      const f = fieldErrors(api);
      if (Object.keys(f).length) setErrors(f);
      else setFormError(api.message);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Settings</p>
          <h1 className="text-h1 text-ink">{s.boutique_name}</h1>
        </div>
        <Button asChild variant="outline"><Link href={`/b/${s.slug}`} target="_blank">View storefront <ExternalLink aria-hidden /></Link></Button>
      </header>
      {formError && <Alert tone="danger">{formError}</Alert>}

      <Card className="grid gap-6 p-6 md:grid-cols-[auto_1fr]">
        <SingleImageField label="Logo" purpose="boutique" url={logo?.url ?? s.logo_url} onUploaded={setLogo} />
        <SingleImageField label="Banner" purpose="boutique" url={banner?.url ?? s.banner_url} onUploaded={setBanner} aspect="wide" />
      </Card>

      <Card className="flex flex-col gap-5 p-6">
        <h2 className="text-h3 text-ink">About & policies</h2>
        <Field label="Tagline" optional><Input value={tagline} onChange={(e) => setTagline(e.target.value)} maxLength={160} /></Field>
        <Field label="About your atelier" error={errors.bio} hint="At least 40 characters."><Textarea rows={5} value={bio} onChange={(e) => setBio(e.target.value)} maxLength={2000} /></Field>
        <Field label="Return policy" error={errors.return_policy}><Textarea rows={3} value={policy} onChange={(e) => setPolicy(e.target.value)} maxLength={2000} /></Field>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Contact email" error={errors.contact_email}><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <Field label="City" error={errors.city}><Input value={city} onChange={(e) => setCity(e.target.value)} maxLength={80} /></Field>
        </div>
      </Card>

      <Card className="flex flex-col gap-4 p-6">
        <div className="flex items-baseline justify-between">
          <h2 className="text-h3 text-ink">Featured pieces</h2>
          <span className="text-caption text-ink-muted">{featured.length}/4 · shown first on your storefront</span>
        </div>
        {products.isPending ? <Skeleton className="h-40 rounded-input" /> : products.data?.items.length ? (
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {products.data.items.map((p) => {
              const on = featured.includes(p.id);
              const order = featured.indexOf(p.id) + 1;
              return (
                <li key={p.id}>
                  <button
                    type="button"
                    aria-pressed={on}
                    disabled={!on && featured.length >= 4}
                    onClick={() => toggle(p.id)}
                    className={cn("flex w-full flex-col gap-1.5 rounded-input border-2 p-1.5 text-left disabled:opacity-40", on ? "border-accent-2" : "border-transparent hover:border-border-strong")}
                  >
                    <span className="relative block aspect-[4/5] overflow-clip rounded-input bg-surface-muted">
                      {p.image && <Image src={p.image} alt="" fill sizes="150px" className="object-cover" />}
                      {on && <span className="absolute left-1.5 top-1.5 grid size-6 place-items-center rounded-full bg-accent-2 text-caption font-bold text-on-accent-2">{order}</span>}
                    </span>
                    <span className="line-clamp-1 text-caption font-semibold text-ink">{p.title}</span>
                    <span className="tabular text-caption text-ink-muted">{formatQc(p.min_price_qc)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-small text-ink-muted">Publish a piece first, then pin it here.</p>
        )}
      </Card>

      <Card className="p-6">
        <SortableImages label="Lookbook" purpose="boutique" items={look} onChange={setLook} max={6} textLabel="Caption" textPlaceholder="Caption (optional)" />
      </Card>

      <div className="sticky bottom-0 -mx-4 flex justify-end border-t border-border bg-bg/95 px-4 py-4 backdrop-blur">
        <Button type="submit" variant="primary" size="lg" loading={save.isPending}>Save storefront</Button>
      </div>
    </form>
  );
}
