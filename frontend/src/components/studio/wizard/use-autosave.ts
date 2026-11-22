"use client";

import { useEffect, useRef, useState } from "react";

import { toApiError } from "@/lib/api/client";

export type SaveState =
  | { kind: "idle" }
  | { kind: "pending" }
  | { kind: "saving" }
  | { kind: "saved"; at: number }
  | { kind: "error"; message: string };

/**
 * Debounced autosave. `value` changes → wait `delay` → `save(value)`.
 * Skips the first render (the value came from the server) and never runs two
 * saves at once; the latest value always wins.
 * UX: Doherty Threshold — a quiet "Saved" instead of a Save button per field.
 */
export function useAutosave<T>(value: T, save: (v: T) => Promise<unknown>, { delay = 900, enabled = true } = {}) {
  const [state, setState] = useState<SaveState>({ kind: "idle" });
  const latest = useRef(value);
  const running = useRef(false);
  const queued = useRef(false);
  const saveRef = useRef(save);
  saveRef.current = save;
  latest.current = value;
  const serialized = JSON.stringify(value);
  // Compare with what was last saved (not "first render"): React's dev double
  // effects and server echoes then never look like unsaved edits.
  const savedAs = useRef(serialized);

  const flush = async () => {
    if (JSON.stringify(latest.current) === savedAs.current) return;
    if (running.current) {
      queued.current = true;
      return;
    }
    running.current = true;
    setState({ kind: "saving" });
    try {
      const sending = JSON.stringify(latest.current);
      await saveRef.current(latest.current);
      savedAs.current = sending;
      setState({ kind: "saved", at: Date.now() });
    } catch (err) {
      setState({ kind: "error", message: toApiError(err).message });
    } finally {
      running.current = false;
      if (queued.current) {
        queued.current = false;
        void flush();
      }
    }
  };

  useEffect(() => {
    if (!enabled || serialized === savedAs.current) return;
    setState({ kind: "pending" });
    const t = setTimeout(() => void flush(), delay);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serialized, enabled, delay]);

  return { state, flush };
}

export function saveLabel(s: SaveState): string {
  switch (s.kind) {
    case "pending":
      return "Unsaved changes…";
    case "saving":
      return "Saving…";
    case "saved":
      return "All changes saved";
    case "error":
      return s.message;
    default:
      return "Drafts save automatically";
  }
}
