"use client";

import { Award, Check, FolderTree, LayoutGrid, Pencil, Plus, Star, Trash2 } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { SingleImageField, type GalleryItem } from "@/components/studio/uploads";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, EmptyState, ErrorState } from "@/components/ui/states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toApiError } from "@/lib/api/client";
import { useAdminCategories, useAdminCollections, useCatalogActions, usePicks, type AdminCategory, type AdminCollection } from "@/lib/admin";
import { formatQc } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Catalog management. UX: Chunking — taxonomy and editorial work live in two
 * tabs; each category is one card. Renames keep slugs, so links never break.
 */
export function CatalogView() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">Merchandising</p>
        <h1 className="text-h1 text-ink">Catalog</h1>
        <p className="text-small text-ink-muted">Featured boutiques are set on the <Link href="/admin/sellers?status=approved" className="font-semibold text-accent-2 underline">Sellers</Link> page.</p>
      </header>
      <Tabs defaultValue="taxonomy" className="flex flex-col gap-6">
        <TabsList>
          <TabsTrigger value="taxonomy"><FolderTree aria-hidden className="size-4" /> Categories &amp; picks</TabsTrigger>
          <TabsTrigger value="collections"><LayoutGrid aria-hidden className="size-4" /> Collections</TabsTrigger>
        </TabsList>
        <TabsContent value="taxonomy"><Taxonomy /></TabsContent>
        <TabsContent value="collections"><Collections /></TabsContent>
      </Tabs>
    </div>
  );
}

// ─── Taxonomy ──────────────────────────────────────────────────────────────

function Taxonomy() {
  const cats = useAdminCategories();
  if (cats.isPending) return <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading categories">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-40 rounded-card" />)}</div>;
  if (cats.isError) return <ErrorState message={toApiError(cats.error).message} onRetry={() => cats.refetch()} />;
  return <div className="flex flex-col gap-4">{cats.data.map((c) => <CategoryCard key={c.id} c={c} />)}</div>;
}

function CategoryCard({ c }: { c: AdminCategory }) {
  const { updateCategory, addSub, updateSub, deleteSub } = useCatalogActions();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(c.name);
  const [tagline, setTagline] = useState(c.tagline ?? "");
  const [sort, setSort] = useState(String(c.sort_order));
  const [newSub, setNewSub] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameText, setRenameText] = useState("");
  const [pickFor, setPickFor] = useState<string | null>(null);
  const [showSchema, setShowSchema] = useState(false);
  const fail = (e: unknown) => toast.error(toApiError(e).message);

  return (
    <Card className="flex flex-col gap-4 p-5">
      {editing ? (
        <form
          className="grid gap-3 sm:grid-cols-[1fr_2fr_100px_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            updateCategory.mutate(
              { id: c.id, body: { name, tagline: tagline || null, sort_order: Number(sort) || 0 } },
              { onSuccess: () => { toast.success(`${name} saved`); setEditing(false); }, onError: fail },
            );
          }}
        >
          <Field label="Name"><Input value={name} maxLength={48} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Tagline" optional><Input value={tagline} maxLength={160} onChange={(e) => setTagline(e.target.value)} /></Field>
          <Field label="Order"><Input inputMode="numeric" value={sort} onChange={(e) => setSort(e.target.value.replace(/\D/g, ""))} /></Field>
          <div className="flex items-end gap-2">
            <Button type="submit" size="sm" variant="primary" loading={updateCategory.isPending}>Save</Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap items-start gap-3">
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="flex items-center gap-2">
              <h2 className="text-h3 text-ink">{c.name}</h2>
              <span className="text-caption text-ink-muted">/{c.slug} · {c.product_count} live pieces</span>
            </div>
            {c.tagline && <p className="text-small text-ink-muted">{c.tagline}</p>}
          </div>
          <Button size="sm" variant="ghost" onClick={() => setShowSchema((s) => !s)}>{showSchema ? "Hide" : "View"} attribute schema</Button>
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}><Pencil aria-hidden /> Edit</Button>
        </div>
      )}
      {showSchema && (
        <pre className="max-h-64 overflow-auto rounded-input bg-surface-muted p-3 text-caption text-ink">{JSON.stringify(c.attribute_schema.properties ?? c.attribute_schema, null, 2)}</pre>
      )}

      <ul className="flex flex-col divide-y divide-border rounded-input border border-border">
        {c.subcategories.map((s) => (
          <li key={s.id} className="flex flex-col gap-2 px-3 py-2">
            <div className="flex flex-wrap items-center gap-2 text-small">
              {renaming === s.id ? (
                <form className="flex flex-1 gap-2" onSubmit={(e) => {
                  e.preventDefault();
                  updateSub.mutate({ id: s.id, body: { name: renameText } }, { onSuccess: () => { toast.success("Renamed (the URL stays the same)"); setRenaming(null); }, onError: fail });
                }}>
                  <Input aria-label={`New name for ${s.name}`} value={renameText} maxLength={48} onChange={(e) => setRenameText(e.target.value)} className="h-10" autoFocus />
                  <Button type="submit" size="sm" variant="primary" loading={updateSub.isPending}>Save</Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setRenaming(null)}>Cancel</Button>
                </form>
              ) : (
                <>
                  <span className="font-semibold text-ink">{s.name}</span>
                  <span className="text-caption text-ink-muted">/{s.slug} · {s.product_count}</span>
                  <div className="ml-auto flex">
                    <Button size="sm" variant="ghost" onClick={() => setPickFor(pickFor === s.id ? null : s.id)} disabled={s.product_count === 0}>
                      <Award aria-hidden /> Pick
                    </Button>
                    <Button size="icon" variant="ghost" aria-label={`Rename ${s.name}`} onClick={() => { setRenaming(s.id); setRenameText(s.name); }}><Pencil aria-hidden /></Button>
                    <Button size="icon" variant="ghost" aria-label={`Delete ${s.name}`} className="text-ink-muted hover:text-danger"
                      onClick={() => deleteSub.mutate(s.id, { onSuccess: () => toast.success(`${s.name} deleted`), onError: fail })}>
                      <Trash2 aria-hidden />
                    </Button>
                  </div>
                </>
              )}
            </div>
            {pickFor === s.id && <Picks subId={s.id} name={s.name} />}
          </li>
        ))}
      </ul>
      <form className="flex gap-2" onSubmit={(e) => {
        e.preventDefault();
        if (newSub.trim().length < 2) return;
        addSub.mutate({ categoryId: c.id, name: newSub }, { onSuccess: () => { toast.success(`${newSub.trim()} added`); setNewSub(""); }, onError: fail });
      }}>
        <Input aria-label={`New ${c.name} subcategory`} placeholder={`New ${c.name.toLowerCase()} subcategory`} value={newSub} maxLength={48} onChange={(e) => setNewSub(e.target.value)} className="h-11 max-w-xs" />
        <Button type="submit" size="sm" variant="outline" loading={addSub.isPending} disabled={newSub.trim().length < 2}><Plus aria-hidden /> Add</Button>
      </form>
    </Card>
  );
}

/** One Connoisseur's pick per subcategory (choosing one clears the previous). */
function Picks({ subId, name }: { subId: string; name: string }) {
  const picks = usePicks(subId);
  const { setPick } = useCatalogActions();
  if (picks.isPending) return <Skeleton className="h-24 rounded-input" />;
  if (picks.isError) return <ErrorState message={toApiError(picks.error).message} onRetry={() => picks.refetch()} />;
  return (
    <div className="flex flex-col gap-2 rounded-input bg-surface-muted p-3">
      <p className="text-caption text-ink-muted">Connoisseur&apos;s pick for {name}: highlighted first in its listing. One per subcategory.</p>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {picks.data.slice(0, 12).map((p) => (
          <li key={p.id}>
            <button type="button" aria-pressed={p.is_pick}
              onClick={() => setPick.mutate({ productId: p.id, on: !p.is_pick }, { onSuccess: () => { toast.success(p.is_pick ? "Pick cleared" : `${p.title} is the pick`); picks.refetch(); }, onError: (e) => toast.error(toApiError(e).message) })}
              className={cn("flex w-full items-center gap-2 rounded-input border-2 bg-surface p-2 text-left text-small", p.is_pick ? "border-accent-2" : "border-transparent hover:border-border-strong")}>
              <span className="relative aspect-[4/5] w-10 shrink-0 overflow-clip rounded-input bg-surface-muted">{p.image && <Image src={p.image} alt="" fill sizes="40px" className="object-cover" />}</span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate font-semibold text-ink">{p.title}</span>
                <span className="truncate text-caption text-ink-muted">{p.boutique} · {formatQc(p.price_qc)}</span>
              </span>
              {p.is_pick && <Check aria-hidden className="size-4 text-accent-2" />}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Collections ───────────────────────────────────────────────────────────

function Collections() {
  const data = useAdminCollections();
  const { deleteCollection } = useCatalogActions();
  const [editing, setEditing] = useState<AdminCollection | "new" | null>(null);
  if (data.isPending) return <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading collections">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-24 rounded-card" />)}</div>;
  if (data.isError) return <ErrorState message={toApiError(data.error).message} onRetry={() => data.refetch()} />;
  const { items, tags } = data.data;

  return (
    <div className="flex flex-col gap-4">
      {editing === null && <Button variant="primary" className="self-start" onClick={() => setEditing("new")}><Plus aria-hidden /> New collection</Button>}
      {editing !== null && <CollectionForm c={editing === "new" ? null : editing} tags={tags} onDone={() => setEditing(null)} />}
      {items.length === 0 ? (
        <EmptyState icon={LayoutGrid} title="No collections" description="Editorial edits group live pieces by tag." />
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {items.map((c) => (
            <li key={c.id}>
              <Card className="flex gap-4 p-4">
                <div className="relative aspect-[4/5] w-20 shrink-0 overflow-clip rounded-input bg-surface-muted">{c.hero_url && <Image src={c.hero_url} alt="" fill sizes="80px" className="object-cover" />}</div>
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  {c.kicker && <span className="text-caption font-bold uppercase tracking-[0.1em] text-ink-muted">{c.kicker}</span>}
                  <Link href={`/collections/${c.slug}`} className="font-semibold text-ink hover:underline">{c.title}</Link>
                  <span className="text-caption text-ink-muted">#{c.tag} · {c.product_count} live pieces · order {c.sort_order}</span>
                  {c.is_featured && <Badge tone="lilac" withIcon={false} className="self-start"><Star aria-hidden className="size-3" /> On the home page</Badge>}
                  <div className="mt-auto flex gap-1">
                    <Button size="sm" variant="ghost" onClick={() => setEditing(c)}><Pencil aria-hidden /> Edit</Button>
                    <Button size="sm" variant="ghost" className="text-ink-muted hover:text-danger"
                      onClick={() => deleteCollection.mutate(c.id, { onSuccess: () => toast.success(`${c.title} deleted`), onError: (e) => toast.error(toApiError(e).message) })}>
                      <Trash2 aria-hidden /> Delete
                    </Button>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CollectionForm({ c, tags, onDone }: { c: AdminCollection | null; tags: { tag: string; products: number }[]; onDone: () => void }) {
  const { saveCollection } = useCatalogActions();
  const [title, setTitle] = useState(c?.title ?? "");
  const [kicker, setKicker] = useState(c?.kicker ?? "");
  const [subtitle, setSubtitle] = useState(c?.subtitle ?? "");
  const [body, setBody] = useState(c?.body ?? "");
  const [tag, setTag] = useState(c?.tag ?? tags[0]?.tag ?? "");
  const [featured, setFeatured] = useState(c?.is_featured ?? false);
  const [sort, setSort] = useState(String(c?.sort_order ?? 0));
  const [hero, setHero] = useState<GalleryItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await saveCollection.mutateAsync({
        id: c?.id,
        body: { title, kicker: kicker || null, subtitle: subtitle || null, body: body || null, tag, is_featured: featured, sort_order: Number(sort) || 0, hero_asset_id: hero?.assetId ?? null },
      });
      toast.success(c ? "Collection saved" : "Collection created");
      onDone();
    } catch (err) {
      setError(toApiError(err).message);
    }
  };

  return (
    <Card className="p-5">
      <form onSubmit={submit} noValidate className="grid gap-4 md:grid-cols-[1fr_auto]">
        <div className="flex flex-col gap-4">
          <h2 className="text-h3 text-ink">{c ? `Edit ${c.title}` : "New collection"}</h2>
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Title"><Input value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></Field>
            <Field label="Kicker" optional><Input value={kicker} maxLength={60} onChange={(e) => setKicker(e.target.value)} placeholder="The edit" /></Field>
          </div>
          <Field label="Subtitle" optional><Input value={subtitle} maxLength={200} onChange={(e) => setSubtitle(e.target.value)} /></Field>
          <Field label="Story" optional><Textarea rows={3} value={body} maxLength={4000} onChange={(e) => setBody(e.target.value)} /></Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Products tagged" hint="Live pieces with this tag appear.">
              <Select value={tag} onChange={(e) => setTag(e.target.value)}>
                {tags.map((t) => <option key={t.tag} value={t.tag}>#{t.tag} ({t.products})</option>)}
              </Select>
            </Field>
            <Field label="Order"><Input inputMode="numeric" value={sort} onChange={(e) => setSort(e.target.value.replace(/\D/g, ""))} /></Field>
            <label className="flex min-h-11 items-center gap-2 self-end text-small font-semibold text-ink">
              <input type="checkbox" checked={featured} onChange={(e) => setFeatured(e.target.checked)} className="size-4 accent-[var(--accent-2)]" />
              Feature on the home page
            </label>
          </div>
          <div className="flex gap-2">
            <Button type="submit" variant="primary" loading={saveCollection.isPending} disabled={title.trim().length < 3 || !tag}>{c ? "Save" : "Create"}</Button>
            <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
          </div>
        </div>
        <SingleImageField label="Hero image" hint="Optional. Portrait works best." purpose="product" url={hero?.url ?? c?.hero_url ?? null} onUploaded={setHero} />
      </form>
    </Card>
  );
}
