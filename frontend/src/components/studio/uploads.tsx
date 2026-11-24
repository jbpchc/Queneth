"use client";

import { ArrowLeft, ArrowRight, GripVertical, ImagePlus, Trash2 } from "lucide-react";
import Image from "next/image";
import { useId, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { uploadImage, type MediaPurpose } from "@/lib/media";
import { cn } from "@/lib/utils";

/** One image in an editable gallery: an existing URL or a fresh upload. */
export interface GalleryItem {
  key: string;
  url: string;
  assetId?: string;
  text: string; // alt text (products) or caption (lookbook)
  /** Product photos: the variant color the photo shows (switches with the swatch). */
  color?: string | null;
}

function useUploader(purpose: MediaPurpose) {
  const [busy, setBusy] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const upload = async (files: FileList | File[], limit: number) => {
    setError(null);
    const out: GalleryItem[] = [];
    for (const file of Array.from(files).slice(0, limit)) {
      setBusy((n) => n + 1);
      try {
        const asset = await uploadImage(file, purpose);
        out.push({ key: asset.id, url: asset.thumbnail_url ?? asset.url ?? "", assetId: asset.id, text: "" });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed. Try again.");
      } finally {
        setBusy((n) => n - 1);
      }
    }
    return out;
  };
  return { upload, busy: busy > 0, error };
}

/** Logo / banner / drop hero: one image, replaced on upload. */
export function SingleImageField({
  label,
  hint,
  purpose,
  url,
  onUploaded,
  aspect = "square",
}: {
  label: string;
  hint?: string;
  purpose: MediaPurpose;
  url: string | null;
  onUploaded: (item: GalleryItem) => void;
  aspect?: "square" | "wide";
}) {
  const id = useId();
  const { upload, busy, error } = useUploader(purpose);
  return (
    <div className="flex flex-col gap-2">
      <span className="text-small font-semibold text-ink">{label}</span>
      <label
        htmlFor={id}
        className={cn(
          "relative grid cursor-pointer place-items-center overflow-clip rounded-input border-2 border-dashed border-border-strong bg-surface-muted text-ink-muted hover:border-ink hover:text-ink",
          aspect === "square" ? "size-28" : "aspect-[3/1] w-full",
        )}
      >
        {url ? <Image src={url} alt="" fill sizes="(min-width: 768px) 480px, 100vw" className="object-cover" /> : <ImagePlus aria-hidden className="size-6" />}
        {busy && <span className="absolute inset-0 grid place-items-center bg-bg/70"><Spinner label="Uploading" /></span>}
        <span className="sr-only">{url ? `Replace ${label.toLowerCase()}` : `Upload ${label.toLowerCase()}`}</span>
      </label>
      <input
        id={id}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        onChange={async (e) => {
          if (!e.target.files?.length) return;
          const [item] = await upload(e.target.files, 1);
          e.target.value = "";
          if (item) onUploaded(item);
        }}
      />
      {hint && <span className="text-caption text-ink-muted">{hint}</span>}
      {error && <span role="alert" className="text-small text-danger">{error}</span>}
    </div>
  );
}

/**
 * Gallery editor. Drag to reorder (the first image is the cover), or use the
 * arrow buttons — the keyboard and screen-reader equivalent of dragging.
 * UX: Fitts's Law — whole tiles are drop targets; controls are 44px.
 */
export function SortableImages({
  label,
  purpose,
  items,
  onChange,
  max,
  textLabel,
  textPlaceholder,
  colors,
}: {
  label: string;
  purpose: MediaPurpose;
  items: GalleryItem[];
  onChange: (items: GalleryItem[]) => void;
  max: number;
  textLabel: string;
  textPlaceholder?: string;
  /** When given, each photo can be tagged with the color it shows. */
  colors?: string[];
}) {
  const id = useId();
  const fileRef = useRef<HTMLInputElement>(null);
  const { upload, busy, error } = useUploader(purpose);
  const [dragging, setDragging] = useState<number | null>(null);

  const move = (from: number, to: number) => {
    if (to < 0 || to >= items.length || from === to) return;
    const next = [...items];
    const [it] = next.splice(from, 1);
    next.splice(to, 0, it!);
    onChange(next);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <span className="text-small font-semibold text-ink">{label}</span>
        <span className="text-caption text-ink-muted">{items.length}/{max}{items.length > 1 && " · drag to reorder"}</span>
      </div>
      <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {items.map((it, i) => (
          <li
            key={it.key}
            draggable
            onDragStart={() => setDragging(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => {
              if (dragging !== null) move(dragging, i);
              setDragging(null);
            }}
            onDragEnd={() => setDragging(null)}
            className={cn("flex flex-col gap-2 rounded-input border border-border bg-surface p-2", dragging === i && "opacity-50")}
          >
            <div className="relative aspect-[4/5] overflow-clip rounded-input bg-surface-muted">
              {it.url && <Image src={it.url} alt={it.text || ""} fill sizes="200px" className="object-cover" />}
              {i === 0 && <span className="absolute left-1.5 top-1.5 rounded-pill bg-ink px-2 py-0.5 text-caption font-bold text-bg">Cover</span>}
              <GripVertical aria-hidden className="absolute right-1.5 top-1.5 size-4 cursor-grab text-bg drop-shadow" />
            </div>
            <Input
              aria-label={`${textLabel} for image ${i + 1}`}
              placeholder={textPlaceholder}
              value={it.text}
              maxLength={200}
              onChange={(e) => onChange(items.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
              className="h-10 text-small"
            />
            {colors && colors.length > 0 && (
              <select
                aria-label={`Color shown in image ${i + 1}`}
                value={it.color && colors.includes(it.color) ? it.color : ""}
                onChange={(e) => onChange(items.map((x, j) => (j === i ? { ...x, color: e.target.value || null } : x)))}
                className="h-10 rounded-input border border-border bg-surface px-2 text-small text-ink"
              >
                <option value="">Any color</option>
                {colors.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            )}
            <div className="flex items-center">
              <button type="button" aria-label={`Move image ${i + 1} earlier`} disabled={i === 0} onClick={() => move(i, i - 1)} className="grid size-11 place-items-center rounded-full disabled:opacity-30 hover:bg-surface-muted">
                <ArrowLeft aria-hidden className="size-4" />
              </button>
              <button type="button" aria-label={`Move image ${i + 1} later`} disabled={i === items.length - 1} onClick={() => move(i, i + 1)} className="grid size-11 place-items-center rounded-full disabled:opacity-30 hover:bg-surface-muted">
                <ArrowRight aria-hidden className="size-4" />
              </button>
              <button type="button" aria-label={`Remove image ${i + 1}`} onClick={() => onChange(items.filter((_, j) => j !== i))} className="ml-auto grid size-11 place-items-center rounded-full text-ink-muted hover:bg-surface-muted hover:text-danger">
                <Trash2 aria-hidden className="size-4" />
              </button>
            </div>
          </li>
        ))}
        {items.length < max && (
          <li>
            <label htmlFor={id} className={cn("grid aspect-[4/5] cursor-pointer place-items-center rounded-input border-2 border-dashed border-border-strong text-small font-semibold text-ink-muted hover:border-ink hover:text-ink", busy && "pointer-events-none opacity-60")}>
              <span className="flex flex-col items-center gap-2">
                {busy ? <Spinner label="Uploading" /> : <ImagePlus aria-hidden className="size-6" />}
                {busy ? "Uploading…" : "Add photos"}
              </span>
            </label>
            <input
              ref={fileRef}
              id={id}
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              onChange={async (e) => {
                if (!e.target.files?.length) return;
                const added = await upload(e.target.files, max - items.length);
                if (fileRef.current) fileRef.current.value = "";
                if (added.length) onChange([...items, ...added]);
              }}
            />
          </li>
        )}
      </ol>
      {error && <p role="alert" className="text-small text-danger">{error}</p>}
    </div>
  );
}
