# Laws of UX — where Queneth applies them

Every application is also marked in code with a `UX:` comment
(`grep -rn "UX:" frontend/src backend/app`). Screenshot placeholders are
filled in during Phase 11 for the capstone defense.

Status: ✅ applied · 🟡 partially (foundation in place) · ⏳ later phase

## Heuristics

| Law | Where it's applied (file → component) | Status | Screenshot |
| --- | --- | --- | --- |
| Jakob's Law | `components/layout/logo.tsx` (logo top-left → home), `site-header.tsx` (search in header), `bag-button.tsx` (bag top-right with count badge), `ui/select.tsx` (native selects) | 🟡 | _placeholder_ |
| Fitts's Law | `admin/reason-form.tsx` (confirm under the question, destructive never default), `studio/uploads.tsx` (whole tiles are drop targets; 44px move/remove buttons), `sub-order-actions.tsx` (confirm sits under the question; destructive never default), `checkout-view.tsx` (sticky full-width Pay bar), `orders-list.tsx` (whole card is the link), `product/purchase-panel.tsx` (sticky full-width 48px Add to Bag on mobile), `bag/bag-view.tsx` (44px steppers, remove kept apart), `(auth)/login/login-form.tsx` (full-width 48px Sign in), `ui/dropdown-menu.tsx` (44px rows), `ui/button.tsx` (44/48px heights, `block` full-width), `ui/input.tsx` (48px fields), `ui/chip.tsx` and `ui/checkbox.tsx` (44px hit areas), `mobile-tab-bar.tsx`; tokens `--hit-min`, `--cta-min` | 🟡 sticky CTAs in Phases 4 and 6 | _placeholder_ |
| Hick's Law | `catalog/report-button.tsx` (five plain reasons), `admin/sellers` (only status-relevant actions), `orders/sub-order-actions.tsx` + `seller/orders` (only the moves the state machine allows), `checkout-view.tsx` (one open step at a time) + `checkout/layout.tsx` (no store nav while paying), `lib/nav.ts` + `site-header.tsx` mega-menu (5 categories, ≤8 subcategories each); `catalog/listing/filter-bar.tsx` (4 key filters, the rest behind *More filters*) | 🟡 checkout in Phase 6 | _placeholder_ |
| Miller's Law & chunking | `admin/catalog` (taxonomy vs collections tabs), audit rows with details on demand, wizard (6 steps), settings (4 sections), `wishlist-view.tsx` (boards), `lib/commerce.formatPhone` (0917 123 4567), `lib/format.ts` `chunkReference()` (QN-2026-4821-07; wallet refs QW-2026-1113-482107), `p/[slug]/page.tsx` details accordion, `listing-results.tsx` + `core/pagination.py` (batches of 24) | ✅ | _placeholder_ |
| Tesler's Law | `studio/wizard/attribute-fields.tsx` (chips/selects, composition total computed for the seller), `order_service.checkout` (split per boutique, vouchers, escrow handled server-side), checkout inline top-up, `components/forms/address-picker.tsx` (official PSGC lists instead of free-typed places; NCR/independent-city quirks absorbed by `geo_service.py`); `lib/media.ts` (Cloudinary → local fallback invisible to the user) | 🟡 cart split in Phase 6 | _placeholder_ |
| Doherty Threshold | `admin/users` (results kept on screen while the next page loads), `studio/wizard/use-autosave.ts` (quiet autosave, "All changes saved"), inventory inline edits, `checkout-view.tsx` (instant Pay feedback; idempotent retries), `lib/shop.ts` (optimistic heart and bag badge), `catalog/follow-button.tsx` (optimistic follow), `product-card.tsx` (prefetch), `ui/skeleton.tsx` (layout-matched skeletons), `(storefront)/loading.tsx`, `db/session.py` (bounded health ping), `account/notifications/inbox.tsx` (optimistic mark-read), `lib/geo.ts` (session-cached PSGC lists) | 🟡 optimistic UI in Phases 6–10 | _placeholder_ |
| Postel's Law | voucher codes (" mira 15 "), withdraw amounts ("12,500"), perfume notes normalized, `schemas/commerce.normalize_ph_mobile`, `voucher_service.normalize` (" lumen10 "), `pin-input.tsx` (autofill), `wallet_service.normalize_code` (" que demo-5000 " works), PIN with spaces, withdraw amounts like "12,500", `schemas/auth.py` (emails trimmed + lower-cased, names whitespace-collapsed), `core/config.py` (flexible origin lists) | 🟡 phone/size/voucher normalizers in Phases 5–6 | _placeholder_ |
| Occam's Razor & Pareto | Scope rule for every phase; polish budget goes to home, listing, product, bag, checkout | ⏳ | _placeholder_ |
| Parkinson's Law | `app/checkout/checkout-view.tsx` (one page, three short steps, default address pre-selected, no account detours) | ✅ | _placeholder_ |

## Gestalt

| Law | Where | Status | Screenshot |
| --- | --- | --- | --- |
| Proximity | `product/purchase-panel.tsx` (price, option pickers, stock and Add to Bag in one group; reviews far below) | ✅ | _placeholder_ |
| Common Region | `admin/wallet` (read-only health separate from money-moving tools), `order-detail.tsx` (one card per boutique: progress, pieces, actions), `bag-view.tsx` + checkout review (one card per boutique), `address-book.tsx`, `account/wallet/wallet-history.tsx` (bounded transaction rows), `bag/bag-view.tsx` (one card per boutique), `ui/card.tsx`, `layout/studio-shell.tsx` (bounded work area), `admin/integrations/integrations-dashboard.tsx` (one panel per API) | 🟡 | _placeholder_ |
| Similarity | `ui/button.tsx` (one button system), `ui/chip.tsx` (one chip), `ui/price.tsx` (one price style) | ✅ | _placeholder_ |
| Uniform Connectedness | `product/product-view.tsx` + `gallery.tsx` (color swatch moves the gallery to that color's image) | 🟡 order timeline in Phase 7 | _placeholder_ |
| Prägnanz | `catalog/product-card.tsx` (image, brand, name, price, heart; second image only on hover) | ✅ | _placeholder_ |

## Cognitive biases & memory

| Law | Where | Status | Screenshot |
| --- | --- | --- | --- |
| Von Restorff effect | inventory (only rows at/below alert level highlighted), `ui/button.tsx` (`primary` reserved for one CTA per view), `ui/badge.tsx` (citrus only when true) | ✅ | _placeholder_ |
| Serial Position effect | `admin/overview-view.tsx` (decisions first), `admin/moderation` (most-reported first), `admin/sellers` (applications tab first), `seller/dashboard-view.tsx` (action items first, analytics after), `seller/orders/seller-orders.tsx` (tabs in work order, Returns right after New), `lib/nav.ts` (New … Boutiques), `mobile-tab-bar.tsx` (Home first, Profile last) | ✅ | _placeholder_ |
| Aesthetic-Usability effect | `styles/tokens.css`, `app/globals.css` (grain, glass header, type scale) | 🟡 | _placeholder_ |
| Peak-End rule | `seller/dashboard-view.tsx` first-sale banner; `app/checkout/success/[id]/success-view.tsx` (one-time brand confetti, drawn check, "Thank you. It's yours."); Phase 10 adds tier-ups | 🟡 | _placeholder_ |
| Goal-Gradient effect | `studio/wizard/product-wizard.tsx` (6-step progress, ticks per finished step), `orders/status-timeline.tsx` (filled track Paid → Completed), `ui/progress.tsx`; `checkout-view.tsx` (step progress bar), `bag-view.tsx` voucher "Add X QC more" | ✅ | _placeholder_ |
| Zeigarnik effect | wizard "Almost there. Still needed:" list (each item jumps to its step); `account/sell` pending state, `bag-view.tsx` "Saved for later", `account/wallet/wallet-view.tsx` ("Set your QueWallet PIN" until done), `(storefront)/account/account-overview.tsx` `VerifyBanner` (unconfirmed email stays visible with a one-tap resend) | 🟡 more in Phases 6, 8 and 10 | _placeholder_ |
| Selective Attention / banner blindness | product page "Report this piece" is a quiet text link, `(storefront)/page.tsx` and `drops/page.tsx` (drops woven into editorial content, no pop-ups) | ✅ | _placeholder_ |
| Mental Model | `account/wallet/*` (familiar e-wallet: balance card, top up, 6-digit PIN pad, statement), `product/modules/*` (size guide, shoe conversion, fragrance pyramid, bag "what fits"), `layout/account-menu.tsx` (Shopping ↔ Seller Studio switcher like familiar multi-account apps), `ui/price.tsx` (wallet glyph, "QC 12,500"), real fashion vocabulary in copy | 🟡 | _placeholder_ |
| Cognitive Load | `orders/review-form.tsx` (stars first, the rest optional; fit only for sized items), `ui/field.tsx` (helper text, inline errors), `(auth)/register/register-form.tsx` (live password checklist), `(auth)/layout.tsx` (one task per screen) | 🟡 wizard in Phase 8 | _placeholder_ |
| Paradox of the Active User | `ui/states.tsx` `EmptyState` (always offers the next action), `ui/tooltip.tsx` | 🟡 | _placeholder_ |
| Flow | `hooks/use-hotkey.ts` + `site-header.tsx` (`/` focuses search); dialogs barred from checkout | 🟡 | _placeholder_ |
| Choice Overload | `lib/listing-params.ts` (6 sorts, default *Curated for you*), `catalog_service.listing` `connoisseur_pick_id` (one highlighted pick per listing) | ✅ | _placeholder_ |
