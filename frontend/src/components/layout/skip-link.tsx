/** WCAG 2.4.1 — the first focusable element jumps straight to page content. */
export function SkipLink() {
  return (
    <a
      href="#main"
      className="fixed left-4 top-3 z-[60] -translate-y-24 rounded-pill bg-ink px-5 py-3 text-small font-semibold text-bg shadow-3 transition-transform focus-visible:translate-y-0"
    >
      Skip to content
    </a>
  );
}
