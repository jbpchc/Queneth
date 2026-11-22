"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

/**
 * Shared state between the purchase panel and the gallery: choosing a color
 * swatch moves the gallery to that color's image (UX: Uniform Connectedness).
 */
const Ctx = createContext<{ color: string | null; setColor: (c: string | null) => void }>({
  color: null,
  setColor: () => undefined,
});

export function ProductViewProvider({ children, initialColor }: { children: ReactNode; initialColor: string | null }) {
  const [color, setColor] = useState(initialColor);
  return <Ctx.Provider value={{ color, setColor }}>{children}</Ctx.Provider>;
}

export const useProductView = () => useContext(Ctx);
