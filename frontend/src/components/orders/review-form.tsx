"use client";

import { Camera, Star, X } from "lucide-react";
import Image from "next/image";
import { useId, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { toApiError } from "@/lib/api/client";
import { useCreateReview, type OrderItem } from "@/lib/commerce";
import { uploadImage, type MediaAsset } from "@/lib/media";
import { cn } from "@/lib/utils";

const RATING_WORDS = ["", "Disappointing", "Not quite", "Good", "Lovely", "Exceptional"];
const FITS = [
  { value: "small", label: "Runs small" },
  { value: "true", label: "True to size" },
  { value: "large", label: "Runs large" },
] as const;

/**
 * Verified-purchase review for one delivered piece.
 * UX: Cognitive Load — stars first (one tap), then optional words and photos.
 * UX: Postel's Law — photos upload straight to Cloudinary and fall back to
 * local storage silently if it's unreachable.
 */
export function ReviewForm({ orderId, item, onDone }: { orderId: string; item: OrderItem; onDone: () => void }) {
  const create = useCreateReview(orderId);
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [fit, setFit] = useState<"small" | "true" | "large" | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [photos, setPhotos] = useState<MediaAsset[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const id = useId();
  // Sizing feedback only makes sense for things you wear in sizes.
  const wearable = "size" in item.options;

  const addPhotos = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files).slice(0, 4 - photos.length)) {
        const asset = await uploadImage(file, "review");
        setPhotos((p) => [...p, asset]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Try again.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!rating) return setError("Choose a star rating.");
    if (body.trim().length < 10) return setError("Write at least a short sentence (10+ characters).");
    setError(null);
    try {
      await create.mutateAsync({
        order_item_id: item.id,
        rating,
        fit: wearable ? fit : null,
        title: title.trim() || null,
        body,
        photo_asset_ids: photos.map((p) => p.id),
      });
      toast.success("Thanks for your review", { description: "It's live on the product page." });
      onDone();
    } catch (err) {
      setError(toApiError(err).message);
    }
  };

  const shown = hover || rating;
  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4 rounded-input border border-border-strong p-4">
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-small font-semibold text-ink">Your rating</legend>
        <div className="flex items-center gap-1" role="radiogroup" aria-label="Rating" onMouseLeave={() => setHover(0)}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={rating === n}
              aria-label={`${n} star${n > 1 ? "s" : ""}`}
              onClick={() => setRating(n)}
              onMouseEnter={() => setHover(n)}
              className="grid size-11 place-items-center rounded-full"
            >
              <Star aria-hidden className={cn("size-7 transition-transform", n <= shown ? "fill-accent text-accent" : "text-border-strong", n === rating && "scale-110")} />
            </button>
          ))}
          <span className="ml-2 text-small text-ink-muted" aria-live="polite">{RATING_WORDS[shown]}</span>
        </div>
      </fieldset>

      {wearable && (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-small font-semibold text-ink">How does it fit? <span className="font-normal text-ink-muted">(optional)</span></legend>
          <div className="flex flex-wrap gap-2">
            {FITS.map((f) => (
              <button
                key={f.value}
                type="button"
                aria-pressed={fit === f.value}
                onClick={() => setFit(fit === f.value ? null : f.value)}
                className="h-11 rounded-pill border border-border-strong px-4 text-small font-semibold aria-pressed:border-ink aria-pressed:bg-ink aria-pressed:text-bg"
              >
                {f.label}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      <label className="flex flex-col gap-1.5 text-small">
        <span className="font-semibold text-ink">Headline <span className="font-normal text-ink-muted">(optional)</span></span>
        <Input value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Lasts all evening" />
      </label>
      <label className="flex flex-col gap-1.5 text-small">
        <span className="font-semibold text-ink">Your review</span>
        <Textarea value={body} rows={3} maxLength={2000} onChange={(e) => setBody(e.target.value)} placeholder="How does it feel, wear, smell? Would you buy it again?" />
      </label>

      <div className="flex flex-col gap-2">
        <span className="text-small font-semibold text-ink">Photos <span className="font-normal text-ink-muted">(up to 4)</span></span>
        <div className="flex flex-wrap gap-2">
          {photos.filter((p) => p.thumbnail_url ?? p.url).map((p) => (
            <div key={p.id} className="relative size-20 overflow-hidden rounded-input bg-surface-muted">
              <Image src={(p.thumbnail_url ?? p.url)!} alt="Your review photo" fill sizes="80px" className="object-cover" />
              <button type="button" onClick={() => setPhotos((all) => all.filter((x) => x.id !== p.id))} aria-label="Remove photo" className="absolute right-0.5 top-0.5 grid size-7 place-items-center rounded-full bg-ink/70 text-bg">
                <X aria-hidden className="size-3.5" />
              </button>
            </div>
          ))}
          {photos.length < 4 && (
            <>
              <input ref={fileRef} id={`${id}-photos`} type="file" accept="image/jpeg,image/png,image/webp" multiple className="sr-only" onChange={(e) => addPhotos(e.target.files)} />
              <label htmlFor={`${id}-photos`} className={cn("grid size-20 cursor-pointer place-items-center rounded-input border-2 border-dashed border-border-strong text-ink-muted hover:border-ink hover:text-ink", uploading && "pointer-events-none opacity-60")}>
                <Camera aria-hidden className="size-5" />
                <span className="sr-only">{uploading ? "Uploading…" : "Add photos"}</span>
              </label>
            </>
          )}
        </div>
      </div>

      {error && <p role="alert" className="text-small text-danger">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={create.isPending} disabled={uploading}>Post review</Button>
        <Button type="button" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}
