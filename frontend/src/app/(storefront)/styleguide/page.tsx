import type { Metadata } from "next";

import { StyleguideContent } from "./styleguide-content";

export const metadata: Metadata = {
  title: "Style guide",
  description: "Every Queneth design token, component and state in one place.",
  robots: { index: false },
};

const sections = [
  ["colors", "Color"],
  ["type", "Typography"],
  ["space", "Space & shape"],
  ["motion", "Motion"],
  ["buttons", "Buttons"],
  ["forms", "Forms"],
  ["chips", "Chips & badges"],
  ["commerce", "Price & cards"],
  ["progress", "Progress"],
  ["disclosure", "Tabs & accordion"],
  ["overlays", "Overlays & toasts"],
  ["states", "States"],
] as const;

export default function StyleguidePage() {
  return (
    <div className="mx-auto max-w-[1536px] px-4 py-12 sm:px-6 lg:px-10">
      <header className="mb-12 flex max-w-3xl flex-col gap-4">
        <p className="text-caption font-bold uppercase tracking-[0.14em] text-ink-muted">
          Queneth design system
        </p>
        <h1 className="text-h1 text-ink">Style guide</h1>
        <p className="max-w-measure text-ink-muted">
          Editorial luxury with dopamine accents: a porcelain-and-ink base, with saturated color
          held back for moments of action and delight. Toggle the theme in the header to check
          both palettes.
        </p>
      </header>
      <div className="grid gap-12 lg:grid-cols-[200px_1fr]">
        <nav aria-label="Style guide sections" className="hidden lg:block">
          <ul className="sticky top-28 flex flex-col gap-0.5">
            {sections.map(([id, label]) => (
              <li key={id}>
                <a
                  href={`#${id}`}
                  className="flex h-10 items-center rounded-input px-3 text-small text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink"
                >
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <StyleguideContent />
      </div>
    </div>
  );
}
