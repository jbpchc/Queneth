"use client";

import { api, CSRF_COOKIE, readCookie, type ApiSchemas } from "@/lib/api/client";

export type MediaAsset = ApiSchemas["MediaAssetOut"];
export type MediaPurpose = ApiSchemas["UploadRequest"]["purpose"];
type Ticket = ApiSchemas["UploadTicket"];

const ALLOWED = ["image/jpeg", "image/png", "image/webp"] as const;
export const MAX_BYTES = 5 * 1024 * 1024;

export class UploadError extends Error {}

/** Client-side pre-check (the API re-checks everything). */
export function checkImage(file: File): string | null {
  if (!ALLOWED.includes(file.type as (typeof ALLOWED)[number])) return "Use a JPEG, PNG or WebP image.";
  if (file.size > MAX_BYTES) return "Images can be up to 5 MB.";
  return null;
}

function post(
  url: string,
  fields: Record<string, string>,
  file: File,
  { withSession, onProgress }: { withSession: boolean; onProgress?: (pct: number) => void },
): Promise<unknown> {
  // XHR (not fetch) so we can report upload progress.
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const [k, v] of Object.entries(fields)) form.append(k, v);
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    if (withSession) {
      xhr.withCredentials = true;
      const csrf = readCookie(CSRF_COOKIE);
      if (csrf) xhr.setRequestHeader("X-CSRF-Token", csrf);
    }
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON error page */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(Object.assign(new UploadError(`Upload failed (${xhr.status})`), { body }));
    };
    xhr.onerror = () => reject(new UploadError("Network error"));
    xhr.send(form);
  });
}

async function uploadLocal(ticket: Ticket, file: File, onProgress?: (pct: number) => void) {
  return (await post(ticket.upload_url, ticket.fields, file, { withSession: true, onProgress })) as MediaAsset;
}

/**
 * Upload one image: ticket → Cloudinary (signed, direct from the browser) →
 * confirm. If Cloudinary can't be reached, ask the API for a local-storage
 * ticket and upload there instead, so the user never sees the outage.
 */
export async function uploadImage(
  file: File,
  purpose: MediaPurpose,
  onProgress?: (pct: number) => void,
): Promise<MediaAsset> {
  const problem = checkImage(file);
  if (problem) throw new UploadError(problem);

  const { data: ticket, error } = await api.POST("/api/v1/media/uploads", {
    body: { purpose, filename: file.name, content_type: file.type as never, size_bytes: file.size },
  });
  if (error || !ticket) throw Object.assign(new UploadError("Couldn't start the upload."), { body: error });

  if (ticket.provider === "local") return uploadLocal(ticket, file, onProgress);

  try {
    const result = (await post(ticket.upload_url, ticket.fields, file, {
      withSession: false, // never send Queneth cookies to Cloudinary
      onProgress,
    })) as ApiSchemas["CloudinaryResult"];
    const { data: asset, error: completeError } = await api.POST("/api/v1/media/uploads/{asset_id}/complete", {
      params: { path: { asset_id: ticket.asset_id } },
      body: result,
    });
    if (completeError || !asset) throw new UploadError("Upload couldn't be confirmed.");
    return asset;
  } catch (err) {
    if (err instanceof UploadError && err.message.startsWith("Upload couldn't")) throw err;
    const { data: local } = await api.POST("/api/v1/media/uploads/{asset_id}/fallback", {
      params: { path: { asset_id: ticket.asset_id } },
    });
    if (!local) throw new UploadError("Upload failed. Try again.");
    return uploadLocal(local, file, onProgress);
  }
}
