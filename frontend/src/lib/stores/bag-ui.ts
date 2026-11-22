import { create } from "zustand";

/**
 * Bag UI state only (badge count, bounce trigger). The bag itself lives on the
 * server; Phase 6 hydrates `count` from /cart and updates it optimistically.
 */
interface BagUiState {
  count: number;
  /** Increments on every add so the badge can replay its bounce animation. */
  pulse: number;
  setCount: (count: number) => void;
  bump: (by?: number) => void;
}

export const useBagUi = create<BagUiState>((set) => ({
  count: 0,
  pulse: 0,
  setCount: (count) => set({ count }),
  bump: (by = 1) => set((s) => ({ count: s.count + by, pulse: s.pulse + 1 })),
}));
