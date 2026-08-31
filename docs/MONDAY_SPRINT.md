# Monday Sprint — customer-journey UX remediation

**Status: COMPLETE (2026-08-31).** All four phases shipped and live on Clawsrv (`http://204.168.249.99:8102/`).
**Source:** External UX review ("UX Optimization Review — Curry Orders",
by Manus AI, reviewed against `main` at `bb5a2fd`).

This is deliberately more detailed than a normal backlog entry (see
`PHASE_2_PLAN.md`'s own Backlog section, which just points here) so a
session with no memory of the review conversation can execute it
directly.

---

## Phase 1 — Fix the date/slot desync (real bug, do first)

### 1a. Order screen doesn't refresh for a changed collection date

**The bug.** `public.views.order()` (`src/public/views.py`) renders
dishes and slots for only the *first* orderable day — that data is
baked into the initial page render, full stop. `order.js`'s day-chip
click handler (`dayChipsEl.addEventListener`, `src/static/js/order.js`)
updates `state.day` and calls `window.BKCart.setDay()`, but never
re-fetches or re-renders the dish list or slot grid, and never clears
`state.slot`/`state.slotId`. `renderSlotGrid()`'s own comment says
outright: "this only ever manages which chip looks selected, never
which ones are clickable."

**Concretely**: a customer picks a slot for tomorrow, then taps
"Wednesday" — the exact same slot grid (tomorrow's) stays on screen,
the same slot stays marked selected, and if they check out, the server
correctly rejects the mismatched `slot_id`/date (`reserve()` requires
the slot to belong to the chosen trading day) — but the customer
experiences that as a late, confusing checkout failure, not a helpful
availability update. A dish available on day 1 but not on the newly
selected day has the identical failure mode.

**Fix.** No HTMX, no new frontend framework — this codebase has zero
JS dependencies by deliberate convention (`checkout.js` already does
its own hand-rolled `fetch()` + JSON pattern; match that):

1. New small JSON endpoint (e.g. `public:api_day_availability`,
   `GET /api/order/day/<date>`) that returns `{dishes: [...], slots:
   [...]}` for a given date, reusing the exact same
   `menu_queries.dishes_for_date()` / `_slot_list_for_day()` helpers
   `order()` already calls for the first day. Clamp the date to the
   orderable horizon server-side the same way `dish_detail()` already
   does (`materialise_days` + horizon check) — never trust an arbitrary
   `?date=` to materialise unbounded rows.
2. `order.js`'s day-chip handler calls this endpoint, replaces the
   dish list and slot grid with the response, and clears
   `state.slot`/`state.slotId` (+ the matching `cart.js` localStorage
   keys) unconditionally on every date change.
3. Any basket line no longer sellable on the new date (dish inactive,
   sold out, or absent) gets removed with a plain-language notice
   shown inline — not a silent drop.
4. "Continue" stays disabled until a slot on the *current* date is
   selected (the existing `ready` gate already does most of this, it
   just needs `state.slot`/`state.slotId` to actually be cleared for it
   to work correctly across a date change).

**Acceptance criteria:**
- Switching days after picking a slot clears that slot and shows only
  the new day's real dishes/slots (server-verified truth, not a client
  guess).
- A basket line that isn't sellable on the newly chosen day is surfaced
  to the customer, not silently kept or silently dropped.
- New browser/integration-level tests: switch days after selecting a
  slot, switch to a day where a basket item is unavailable, confirm no
  stale `slot_id` can reach `POST /api/checkout`.

### 1b. Checkout capacity-error recovery is a dead end

**The bug.** `public/api.py`'s checkout view already returns rich
recovery data on a capacity conflict — `error` code, `alternatives`
(suggested open slots), `line_index` (which basket line is the
problem). `checkout.js` only ever reads `result.body.message` and
`result.body.fields` — `alternatives`/`error`/`line_index` are parsed
and thrown away. The only recovery path shown to the customer is "Back
to the menu," after they've already typed their name, mobile number,
note, and accepted policies. Separately, `resp.json()` is called with
no `Content-Type` check first, so a non-JSON failure (a proxy error
page, say) degrades to a generic, misleading "couldn't reach the
server" message.

**Fix** (same JS file, no new endpoint needed — the API already sends
what's required):
1. On `slot_full`/`slot_closed`, render the server's `alternatives` as
   clickable slot buttons that resubmit with the new `slot_id`, no
   navigation away from checkout.
2. On `dish_unavailable`/`dish_qty_exceeded`, highlight the specific
   basket line (`line_index`) with an edit/remove action, not a generic
   top-of-form error.
3. On `day_full`, offer the next open date.
4. Check `resp.headers.get('Content-Type')` includes `application/json`
   before calling `resp.json()`; show a distinct, truthful
   "something went wrong on our end" state otherwise, not the generic
   connection-error copy.
5. Preserve every already-entered form value through all of the above
   (name/mobile/note/policy-acceptance must never be cleared by a
   capacity-conflict retry).

**Acceptance criteria:** a slot filling between page-load and submit is
recoverable in-place, in one or two clicks, without losing anything
already typed.

---

## Phase 2 — Reduce friction in the core mobile flow

- **Live configured price**: on dish detail, show a running
  currency-formatted total next to the quantity/option controls
  (`dish.js` already computes `unitPrice`, it's just never displayed
  before the click) and change the CTA to something like *"Add 2 for
  R 180.00."* Use `fieldset`/`legend` for required option groups; default
  selection must skip a disabled/unavailable option value.
- **Inline "Change collection time" in checkout** instead of forcing a
  full return to `/order/`.
- **Consistent payment-timing copy** across home/checkout/status — one
  short, specific sentence for EFT (hold duration, what happens after
  proof upload) and the cash equivalent, not slightly different wording
  per screen.
- **Real mobile breakpoint** (the current one is an explicitly-labeled
  stopgap — see `order.html`'s own CSS comment): ~480px breakpoint,
  `repeat(auto-fit, minmax(88px, 1fr))` or a 2-column slot grid, 16px
  outer padding, 44px minimum on primary tap targets (WCAG 2.2's
  enhanced benchmark, current buttons are 36px).
- **Menu → order path**: link each homepage "Today's picks" dish to its
  detail/order route (currently static, dead-end content); add a bottom
  "Start an order" CTA on the long `/menu/` page. The Order/Checkout
  header icons (already shipped this session) keep their `title`/
  `aria-label`; consider whether they need a visible text label too once
  real usage data exists — the review's suggestion, worth revisiting
  with Phase 4's funnel data rather than guessing now.
- **Homepage hero: get the message + primary CTA above the fold on
  mobile.** Raised separately by the owner's web-designer contact
  ("heading is hard to read and very text-heavy... make the primary
  action and primary message visible without scrolling — think of it as
  an ad"). Checked against the actual template before adding this:
  above "Today's picks" the hero currently stacks a dateline strip, the
  large CMYK-effect headline (`clamp(52px, 11.2vw, 158px)`, 56px margin
  below it), an eyebrow, a second headline, a lead paragraph, the CTA
  row, *then* a three-stat row — six-plus text elements before the
  picks section, and on a real phone (sticky header + that much
  vertical stacking) it's plausible "View the menu" sits below the
  fold before any scrolling. That part of the feedback holds up.
  The CMYK-layered headline itself is a deliberate signature brand
  device (documented throughout the codebase as the intentional
  "distinctive, not a restaurant chain" choice, `print-plates.js`/
  `home.html`'s own comments) — trading legibility for style is an
  inherent property of that effect, not an oversight, so "hard to
  read" is a real but expected trade-off, not a bug. **Tighten the
  hero to lead with message + one clear CTA visible without scrolling
  on a real phone viewport; keep the CMYK headline as a brand asset but
  shrink its footprint or trim what sits above it — get the owner's
  sign-off on the specific treatment before implementing, this is a
  brand call, not a pure UX fix.**

**Test at**: 320px, 375px, 768px widths. **Definition of done**: no
forced backtracking to change something routine (time, quantity) mid-
checkout; homepage message + primary CTA visible without scrolling at
375px.

---

## Phase 3 — Accessibility pass

All of these are real WCAG-mapped gaps, not generic boilerplate advice
— confirmed against the actual markup:

| Area | Fix |
|---|---|
| Dynamic feedback (cart badge, "Added" confirmation, upload status, checkout errors, share status) | `role="status"`/`aria-live="polite"` for ordinary confirmations, `role="alert"` for submission errors. Don't announce every cosmetic update. |
| Checkout error fields | `aria-describedby` linking input to its error text, `aria-invalid` when relevant, clear an individual field's error on change (not only on next submit), move focus to the first invalid field or an error summary after a failed submit. |
| Date/slot chip selection | Currently CSS-only selected state on `<button>`s — add `aria-pressed` (or move to a real radio-group pattern). |
| Document structure | Dish names and option groups are generic `div`s — use real heading elements and `fieldset`/`legend`. Add a skip-to-main-content link. |
| Sold-out dish display | Currently reduces *all* text (name, price) to low opacity — keep name/price/status readable at normal contrast, reserve muting for genuinely decorative elements only. |

**Definition of done**: a keyboard-only pass and a screen-reader pass
through the full order→checkout→status journey both get announced
feedback at every state change, with a working recovery path from every
error.

---

## Phase 4 — Resilience, performance, measurement (after pilot data exists)

- Scope `print-plates.js` (currently loaded unconditionally on every
  public page via `base.html`, including the checkout/payment form) to
  the landing page only — it's a nice brand device, not something a
  payment screen needs to spend battery/GPU on.
- `localStorage` failure handling: don't silently swallow a write
  failure (private browsing, storage quota); add a `storage` event
  listener so a second tab's cart changes reflect in the current tab;
  validate parsed day/slot values before trusting them.
- Real dish photography, once available (blocked on owner content, not
  code) — one consistently cropped image per dish card, honest
  home-kitchen photography, not stock imagery.
- Anonymized funnel events once Phase 1–3 are live: date changed, item
  added, checkout entered, validation failed, capacity conflict shown,
  payment method selected, order created, proof uploaded. Session/
  device-class only — never attach to a name, mobile number, or order
  token. This is what should actually decide whether the *next* round
  of work is photos, copy, payment guidance, or slot tuning — not
  another guess.

---

## What's explicitly NOT in this sprint

Per the review's own scope and this session's earlier backlog entries
(`PHASE_2_PLAN.md`'s Backlog section) — not part of Monday, still
tracked separately:
- Owner operating manual for Brandon.
- Google OAuth staff login.
- Brand direction (Roti Connect vs. Brandon's Kitchen).
- M10's remaining deferred items (reports, retention/backup automation,
  Clawsrv Caddy/TLS, load/security test passes) — see
  `PHASE_2_PLAN.md`.
