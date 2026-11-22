"use client";

import { Camera } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Avatar } from "@/components/ui/avatar";
import { ProgressRing } from "@/components/ui/progress";
import { toApiError } from "@/lib/api/client";
import { useUpdateProfile } from "@/lib/auth/session";
import { UploadError, uploadImage } from "@/lib/media";

/** Tap the avatar to replace it. Uploads via Cloudinary (or the local fallback). */
export function AvatarUploader({ name, src, size = 80 }: { name: string; src?: string | null; size?: number }) {
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const update = useUpdateProfile();

  async function onFile(file: File | undefined) {
    if (!file) return;
    setProgress(0);
    try {
      const asset = await uploadImage(file, "avatar", setProgress);
      await update.mutateAsync({ avatar_asset_id: asset.id });
      toast.success("Photo updated");
    } catch (err) {
      const message =
        err instanceof UploadError
          ? err.message
          : toApiError((err as { body?: unknown })?.body ?? err).message;
      toast.error("Couldn't update your photo", { description: message });
    } finally {
      setProgress(null);
      if (input.current) input.current.value = "";
    }
  }

  const busy = progress !== null;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      {busy ? (
        <ProgressRing value={progress} size={size} stroke={5} label="Uploading photo">
          <span className="tabular text-small font-semibold text-ink">{progress}%</span>
        </ProgressRing>
      ) : (
        <Avatar name={name} src={src} size={size} />
      )}
      <button
        type="button"
        onClick={() => input.current?.click()}
        disabled={busy}
        aria-label="Change profile photo"
        className="absolute -bottom-1 -right-1 grid size-11 place-items-center rounded-full border border-border bg-surface text-ink shadow-2 transition-colors hover:bg-surface-muted disabled:opacity-50"
      >
        <Camera aria-hidden className="size-5" />
      </button>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => onFile(e.target.files?.[0])}
      />
    </div>
  );
}
