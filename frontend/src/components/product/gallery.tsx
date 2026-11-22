"use client";

import { ZoomIn } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import type { ApiSchemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

import { useProductView } from "./product-view";

type Img = ApiSchemas["ImageOut"];

/**
 * Product gallery: big hero image, thumbnails on desktop, swipeable
 * scroll-snap strip on mobile, click to zoom. Follows the selected color.
 */
export function Gallery({ images, title }: { images: Img[]; title: string }) {
  const { color } = useProductView();
  const [index, setIndex] = useState(0);
  const [zoom, setZoom] = useState(false);
  const strip = useRef<HTMLUListElement>(null);
  const reduce = useReducedMotion();

  // Swatch → image: jump to the first image of the chosen color. The
  // preselected color doesn't count, so the page opens on the cover photo.
  const prevColor = useRef(color);
  useEffect(() => {
    if (!color || color === prevColor.current) return;
    prevColor.current = color;
    const i = images.findIndex((img) => img.color === color);
    if (i >= 0) {
      setIndex(i);
      strip.current?.children[i]?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", inline: "start", block: "nearest" });
    }
  }, [color, images, reduce]);

  const current = images[index] ?? images[0];
  if (!current) return null;

  return (
    <div className="flex flex-col gap-3 md:flex-row-reverse md:gap-4">
      {/* Desktop hero */}
      <button
        type="button"
        onClick={() => setZoom(true)}
        className="group relative hidden aspect-[4/5] flex-1 overflow-hidden rounded-card bg-surface-muted md:block"
        aria-label={`Zoom image: ${current.alt}`}
      >
        <AnimatePresence initial={false} mode="popLayout">
          <motion.div
            key={current.url}
            className="absolute inset-0"
            initial={{ opacity: 0, scale: reduce ? 1 : 1.02 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          >
            <Image src={current.url} alt={current.alt} fill priority sizes="(min-width: 1024px) 45vw, 100vw" className="object-cover" />
          </motion.div>
        </AnimatePresence>
        <span className="absolute bottom-4 right-4 grid size-11 place-items-center rounded-full bg-surface/80 opacity-0 shadow-1 backdrop-blur transition-opacity group-hover:opacity-100">
          <ZoomIn aria-hidden className="size-5" />
        </span>
      </button>

      {/* Desktop thumbnails */}
      <ul className="hidden w-20 shrink-0 flex-col gap-3 md:flex" aria-label="Images">
        {images.map((img, i) => (
          <li key={img.url}>
            <button
              type="button"
              onClick={() => setIndex(i)}
              aria-label={`Show ${img.alt}`}
              aria-current={i === index}
              className={cn(
                "relative block aspect-[4/5] w-full overflow-hidden rounded-input bg-surface-muted ring-offset-2 ring-offset-bg transition-shadow",
                i === index ? "ring-2 ring-ink" : "opacity-80 hover:opacity-100",
              )}
            >
              <Image src={img.url} alt="" fill sizes="80px" className="object-cover" />
            </button>
          </li>
        ))}
      </ul>

      {/* Mobile: swipe strip */}
      <ul
        ref={strip}
        className="-mx-4 flex snap-x snap-mandatory gap-2 overflow-x-auto px-4 md:hidden"
        aria-label={`${title} images`}
        onScroll={(e) => {
          const el = e.currentTarget;
          const i = Math.round(el.scrollLeft / (el.firstElementChild?.clientWidth ?? el.clientWidth));
          if (i !== index) setIndex(Math.max(0, Math.min(images.length - 1, i)));
        }}
      >
        {images.map((img, i) => (
          <li key={img.url} className="relative aspect-[4/5] w-[86vw] shrink-0 snap-center overflow-hidden rounded-card bg-surface-muted">
            <button type="button" className="absolute inset-0" onClick={() => { setIndex(i); setZoom(true); }} aria-label={`Zoom image: ${img.alt}`}>
              <Image src={img.url} alt={img.alt} fill priority={i === 0} sizes="86vw" className="object-cover" />
            </button>
          </li>
        ))}
      </ul>
      <p className="tabular text-center text-caption text-ink-muted md:hidden" aria-live="polite">
        {index + 1} / {images.length}
      </p>

      <Dialog open={zoom} onOpenChange={setZoom}>
        <DialogContent className="max-w-[min(92vw,900px)] p-3 sm:p-4" aria-describedby={undefined}>
          <DialogTitle className="sr-only">{current.alt}</DialogTitle>
          <div className="relative aspect-[4/5] max-h-[82dvh] w-full overflow-hidden rounded-input bg-surface-muted">
            <Image src={current.url} alt={current.alt} fill sizes="900px" className="object-contain" />
          </div>
          <div className="mt-3 flex justify-center gap-2">
            {images.map((img, i) => (
              <button
                key={img.url}
                type="button"
                onClick={() => setIndex(i)}
                aria-label={`Show ${img.alt}`}
                className={cn("size-2.5 rounded-full transition-colors", i === index ? "bg-ink" : "bg-border-strong")}
              />
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
