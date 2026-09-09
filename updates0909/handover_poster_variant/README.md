# Handover: Roti Connect — poster variant, mobile

## Overview

Roti Connect is a home kitchen in Windsor Park, Kraaifontein, selling a weekly Friday food drop for collection. The repo is `alboogycOdR/curry-orders` — Django with server-rendered templates, Postgres, self-hosted. The customer surface already exists under `src/templates/public/` in a light editorial style (Broadsheet).

This handover replaces that customer surface with the **poster variant**: a dark, promotional, owner-led design derived from the client's own flyer. The full specification is `Roti Connect Poster Variant - Design & Style Guide.md`, included here. **That document is the source of truth.** This README explains what was built against it, what changed, and what is still open.

The design is mobile. Every measurement below is the mobile value.

## About the design file

`design/Roti Connect — mobile flow (poster).dc.html` is a **design reference created in HTML.** Open it directly in a browser and click through it — hero, collection panel, filtered menu, promise panel, ordering steps, final CTA, footer, plus the basket drawer, order-lookup modal and a checkout screen.

It is not production code. Do not port it. Specifically:

- `support.js` and the `<x-dc>` / `{{ hole }}` syntax belong to the design tool. Note the collision: `{{ }}` here is **not** Django template syntax.
- The `.pv-phone` / `.pv-status` / `.pv-stage` wrapper is a phone mock for viewing. It has no production equivalent; `.pv-screen` is the viewport.
- Everything is scoped under a `.pv` root that carries the tokens. In Django, put the tokens on `body.route-public` (see "Setup") and drop the `.pv` prefix, or keep it as a namespace — your call, but be consistent.

Recreate the design as Django templates using the project's existing patterns: `base.html` plus per-view templates, `{% static %}`, Django forms, and the plain-JS approach the repo already uses (no framework, no CDN — CSP `script-src` is `'self'` only, per `config/security_headers.py`).

## Fidelity

**High-fidelity.** Colours, type, spacing, radii, shadows and motion are specified in the style guide and implemented in the reference. Where this README gives a value, it is the intended value.

Not final: all promotion content (see "Content and data"), and the imagery (see "Assets").

## What this replaces

The current customer templates were built from an earlier, light editorial handover. The poster variant supersedes them. Concretely:

| Now | Becomes |
| --- | --- |
| `broadsheet.css` tokens on `body.route-public` | Poster tokens (below) |
| Source Serif 4 | Barlow Condensed + a script accent |
| Warm paper `#F6F4F1` ground | Navy `#071124` ground, light `#F7F8FA` content sections |
| Teal `#0E5C66` / maroon `#9B1B4A` | Electric blue `#168CFF` / gold `#FFC400` |
| Five-tab bottom nav (Home, Menu, Basket, Account, More) | Four-tab (Home, Menu, Basket, Orders) — guide §10.4 |
| `/basket/` as a page | Basket as a right-sliding drawer — guide §9.3 |
| `/order/` menu page + item sheet overlay | Menu as a section of the single page, add/qty directly on the card |
| Order lookup page | Order lookup as a modal — guide §9.4 |

The **staff** boards (`src/templates/staff/`) are out of scope and keep their current styling. Only `body.route-public` retokens. Check that nothing in `broadsheet.css` used by the staff templates depends on the values you are about to change.

One consequence worth deciding early: the guide's architecture (§8.1) is a single scrolling promotional page, not the current multi-page flow. The reference implements it that way. If you keep separate Django URLs for the sections, keep the visual panel structure regardless.

## Setup

1. Add the poster tokens to `src/static/css/broadsheet.css` under `body.route-public`, replacing the current customer block. Do not touch the `:root` block — that is the staff surface.
2. Load Barlow Condensed (400–900, plus 700 italic). Self-host it. A South African audience on mobile data will feel a webfont round-trip, and the CSP forbids the Google Fonts CDN anyway.
   ```
   font-family: "Barlow Condensed", "Arial Narrow", Arial, sans-serif;
   ```
   The script accent falls back to `"Brush Script MT", "Segoe Script", cursive`. Guide §5.1 wants a licensed script face before production; until then the fallback renders inconsistently across platforms. It must never carry operational information.
3. Copy `design/assets/poster/food-crop.jpg` and `owner-portrait.jpg` into `src/static/img/`. See "Assets" — these are interim.
4. Delete the now-unused `print-plates.js` and any `.cmyk` markup from the customer templates. The poster variant has no print treatments.

## Design tokens

Take every value from a variable. Guide §4 is explicit: do not scatter raw hexes.

**Colour**

| Token | Hex | Used for |
| --- | --- | --- |
| `--poster-navy` | `#071124` | Primary dark ground; text on light surfaces |
| `--poster-black` | `#050A15` | Promo strip, footer, tab bar |
| `--poster-blue` | `#168CFF` | Borders, active states, icons, section rules |
| `--poster-blue-deep` | `#0C3679` | Illustration rings, final CTA panel |
| `--poster-blue-panel` | `#102A58` | Collection card, card image ground |
| `--poster-gold` | `#FFC400` | Prices, primary CTA, badges, active tab |
| `--poster-gold-soft` | `#FFD95A` | Hover only |
| `--poster-white` | `#FFFFFF` | Cards, hero text |
| `--poster-paper` | `#F7F8FA` | Light content sections, drawer |
| `--poster-border` | `#D3DDEA` | Light-surface borders |
| `--poster-muted` | `#56647A` | Secondary copy on light |
| `--poster-muted-dark` | `#AEB8C9` | Secondary copy on dark |
| `--poster-error` | `#D9343E` | Errors, sold-out |
| `--poster-success` | `#55A868` | Confirmed — only when operationally true |

Hierarchy (§4.2): navy sets the environment, white carries readability, blue marks interaction and structure, gold marks value and action. **Gold is rationed** — if everything is gold, the price and the primary CTA stop being special.

Contrast rules that bite in practice: never blue-gray text on navy for required information; never gold text on white for body copy; never blue on a blue panel without a white or border separation.

**Shadows** — hard poster offsets, never soft blurs:
```css
--shadow-gold-offset: 5px 6px 0 #FFC400;
--shadow-blue-offset: 4px 4px 0 #0C55B0;
--shadow-dark-offset: 6px 7px 0 #071124;
--shadow-drawer:     -20px 0 55px rgba(0,0,0,.35);
```

**Motion** — `--ease-poster: cubic-bezier(0.23, 1, 0.32, 1)`. Button press 120–180ms, card hover 180–240ms, hero entry 500–700ms, drawer 280–400ms, modal 220–340ms. Under `prefers-reduced-motion` drop entrance movement entirely and keep colour and border feedback; overlays stay functional with immediate transitions.

**Spacing** — 4px base. The reference uses 18px mobile side padding throughout, per §6.1.

**Radii** — 4–6px on buttons, cards and the collection card; 3–5px on inputs; circular only on the avatar rings. Pills are allowed for compact filters and status labels and nowhere else. This is a graphic, square-ish system.

## Type scale as built

All Barlow Condensed unless noted.

| Role | Size | Weight | Other |
| --- | --- | --- | --- |
| Hero display | 72px | 900 | line-height .8, `text-shadow: 3px 4px 0 rgba(12,54,121,.85)` |
| Script accent | 58px | 700 | script face, gold, no shadow — one word only |
| Section display | 56px | 900 | line-height .82, uppercase |
| Drawer / modal title | 26–34px | 900 | uppercase |
| Menu card title | 22px | 900 | uppercase, line-height .95 |
| Price (hero sticker) | 40px | 900 | |
| Price (card) | 26px | 900 | |
| Body large | 15px | 500 | hero lede, max 32ch |
| Body default | 13px | 500 | descriptions |
| Button | 14px | 900 | uppercase, letter-spacing .12em |
| Eyebrow / section number | 10–11px | 900 | uppercase, letter-spacing .18–.2em |
| Metadata | 9.5–12px | 800–900 | uppercase, tracked |

Only three voices are permitted: condensed display, script accent, utility text. Uppercase for headlines and section titles; keep the hero to two or three lines.

## Screens and components

The reference is one scrolling page plus two overlays and a checkout screen. Section order follows guide §8.1.

### Promo strip
Black bar, gold uppercase, 9.5px. **Three items only** — date, deadline, phone. The dish name was dropped: four items clip below 390px and the dish name is already the hero headline. Phone is a `tel:` link.

### Header
Sticky, navy, 2px blue bottom rule. Owner avatar (38px circle, navy + blue double ring via layered `box-shadow`), "Roti **Connect**" wordmark with the second word in gold, and a bordered basket button carrying a gold count badge. Secondary navigation lives in the bottom bar, per §8.3.

### Hero
Navy, with two rotated translucent blue "brush" bars behind the content (§3.3). Gold eyebrow block "Friday kitchen drop". Headline "MINCE CURRY" with "roti." in gold script beneath. Lede at 32ch.

The art block is the poster composition: owner portrait in a circular white-and-blue ring at lower left, food plate in a bordered rectangle with a dark offset at upper right, and a rotated gold price sticker (`R45` / `PER ROTI`) with a blue offset overlapping the plate's bottom edge. Do not centre these; the overlap is the point.

Primary CTA "Order the special" (gold, blue offset), secondary "Collection details" (blue outline). Below, a three-column proof row: Date / From / Collect.

### Collection panel
Light section. Section number `01 — COLLECTION`, headline "Lunch or dinner. Same big flavour."

The card is a navy panel with a blue border and a **gold offset shadow**. Rows for Available / Where / Method, then a three-column slot grid. Slots are 44px minimum, transparent with a blue border; selected takes a blue fill plus a small gold offset; full slots drop to muted with a line-through and are disabled.

Slot data in the reference: 11:00–13:30 in 30-minute steps, 12:00 full. Real slots come from the capacity system.

### Menu panel
`02 — MENU`, "Order the good stuff.", limited-batch line. Horizontally scrolling category filters — Everything, Roti specials, Roti rolls, Curry pots, Big plates — active state blue with a gold offset, `aria-selected` set, no page reload.

Cards are horizontal: **40% image, 60% content** (§10.3). White, 2px border, 5px radius. The featured card takes a blue border and the gold offset. Each card carries a gold tag (optional), blue uppercase category, uppercase dish name, one-line description, price, and either a navy `+` button or a quantity stepper once in the basket. Sold-out cards drop to 60% opacity with a struck-through name and a red "Sold out" label instead of the add control.

Cards with no photograph take a placeholder: a blue plate-outline SVG centred on the navy panel. This is deliberate — the guide requires an image on every card, and a bare panel reads as a failed load.

### Promise panel
Navy. `03 — THE KITCHEN`, "Experience the taste." Owner portrait at 170px with three concentric rings (white, blue, translucent blue). Three numbered lines with gold numerals on hairline rules.

### Ordering steps
Light. `04 — HOW IT WORKS`, "From click to curry." Three white cards with a 6px blue left border: Pick your food / Confirm and pay / Collect happy. Followed by a navy notice carrying the EFT hold and the cash cap.

### Final CTA
Deep blue panel, "Bring the appetite. We'll bring the roti.", deadline line, gold block button.

### Footer
Black. Avatar, wordmark, location paragraph, phone at 28px gold as a `tel:` link, then Menu / Collection / Find my order / WhatsApp.

### Bottom navigation
Fixed, 72px, black, 2px blue top rule, four items: Home, Menu, Basket, Orders. Active takes gold plus a 3px gold bar across the top of the cell. Basket carries a gold count badge. Targets are 44px minimum and the page reserves 96px of bottom padding so nothing hides behind it.

### Basket drawer
Slides from the right, 88% width, paper-white with navy text. Navy header with a close button. Lines carry name, unit price, a quantity stepper and a line total. A collection block repeats the day, location and slot grid — **note the slot chips need a light-surface variant here** (navy on white); the navy-card styling is invisible on paper. Footer pins the total, the hold note and the checkout button, disabled until a slot is chosen. Empty state gets its own heading and a "Browse the menu" CTA.

### Order lookup modal
White, 3px blue border, gold offset. Navy icon block, visible label, mobile number input, "Find order" button. Escape closes it, as it does the drawer.

### Checkout
Light screen. Order summary, total, two payment options (EFT / cash) as bordered rows that take a blue border and gold offset when selected, then name and mobile fields. The place button is disabled until there is a basket, a slot, a name and a number.

## Interactions

| Interaction | Behaviour |
| --- | --- |
| Add / +/− | Mutates the basket; card control swaps between `+` and stepper at the 0/1 boundary; header and tab badges update |
| Category filter | Client-side, no reload, `aria-selected` maintained |
| Slot select | Single-select, full slots inert |
| Basket / Orders tabs | Open the drawer and modal respectively; Escape closes both |
| Hero and footer CTAs | Smooth-scroll to the menu or collection section |
| Checkout | Disabled until basket + slot + name + number |
| Focus | 2px ring, **gold on navy surfaces, blue on light ones**, 2px offset |

Focus styling is not optional and there is no stylesheet to inherit it from — the UA default is a 1px near-black ring that is invisible on `#071124`. Author it once, globally.

## Content and data

Everything below is promotion content and **must be dynamic** (§1.2, §14.3). Do not hard-code this Friday into the application.

| Field | Current value |
| --- | --- |
| Featured dish | Mince Curry Roti |
| Featured price | R45 |
| Promotion date | Friday 04/09 |
| Order deadline | 03/09 |
| Available from | 11:00 |
| Location | Windsor Park, Kraaifontein |
| Method | Direct collection; Uber Courier on request |
| Phone | 082 602 3031 |

The menu behind the featured dish reuses the repo's existing dishes, recategorised into the guide's five categories. Prices are the repo's. Real dishes, prices, availability, slots and the cash cap all come from the existing backend.

**Placeholder honesty (§14.4).** Checkout and order lookup are not wired in the reference, and both say so on screen. There is no fake order number, no fake confirmation, and no claim that a slot is reserved. Keep that discipline until the real endpoints are connected — the existing `POST /api/checkout` and the order-status page already exist in the repo and should be reused rather than rebuilt.

## Assets

`design/assets/poster/` holds two crops I made from the client's flyer:

- `food-crop.jpg` — the roti, cropped clear of the flyer's baked-in text. Used for the hero plate and the featured card.
- `owner-portrait.jpg` — head and shoulders, cropped out of the logo lockup.

Both are **interim**. The full flyer must never be used as an image (§14.5): its text duplicates the live HTML, and at one point produced three Roti Connect logos in a single viewport and a headline that disagreed with the photograph. `source-art/` holds the two originals for reference only.

`hero-dish.jpg` (from the repo) is on Steak Curry & Roti. Seven of the nine dishes have no photograph and take the placeholder.

Ask the client for, per §7.3: a transparent character PNG and an SVG logo, a high-resolution food photo without flyer text, per-dish photography, and the brand font files or permission to use a match.

## Open questions — settle these before building

1. **The phone number disagrees with itself.** The flyer reads 082 602 **3931**; the style guide reads 082 602 **3031**. The reference uses the guide's. Confirm which is correct — it is in the strip, the footer and two `tel:` links.
2. **Uber Courier** — a real selectable fulfilment option, or promotional wording only? It currently appears as a line of text, not a choice.
3. **Public-facing name** — "Roti Connect" or the promotion name, per §16.2.
4. **Single page or keep the URLs?** The guide's architecture is one scrolling page. The repo has `/order/`, `/basket/`, `/checkout/`, `/orders/<token>/`. Decide before splitting templates.
5. **Order status page** — the repo has a full one (EFT bank details, proof upload, five-dot stepper). It has not been restyled to the poster variant. It needs to be.
6. **Account / customer login** — exists in the repo, has no home in the four-tab bar. Folded under Orders, or a fifth tab?

## Not yet designed

Loading states, server-error states, the slot-sold-out-while-deciding race, toasts (§9.5 specifies the copy pattern — name the item, never "Success"), and the tablet and desktop breakpoints (§10.1, §10.5 — the desktop hero is a two-column poster composition with overlapping art). Worth a design pass rather than a developer guess.

## Files in this bundle

```
Roti Connect Poster Variant - Design & Style Guide.md   The specification — source of truth
design/
  Roti Connect — mobile flow (poster).dc.html   The design reference — open in a browser
  assets/poster/food-crop.jpg                   Hero + featured card image (interim)
  assets/poster/owner-portrait.jpg              Avatar and rings (interim)
  src/static/img/hero-dish.jpg                  Steak Curry & Roti
  support.js                                    Design-tool runtime — do not port
source-art/
  roti-connect-advert.jpg                       Client flyer — reference only, never rendered
  roti-connect-owner.jpg                        Logo lockup — reference only
reference/
  Roti Connect — mobile flow (broadsheet).dc.html   The previous light variant, for comparison
```
