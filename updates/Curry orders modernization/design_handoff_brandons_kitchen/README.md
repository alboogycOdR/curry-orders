# Handoff: Brandon's Kitchen — customer site & kitchen desk

## Overview

Brandon's Kitchen is a home-based curry kitchen in Cape Town (repo: `alboogycOdR/curry-orders`, Django/Postgres, self-hosted). It is collection-only with hard daily capacity limits, a same-day cut-off, and a capped cash allowance.

This handoff replaces the dark single-page marketing prototype at `design/prototype/index.html` with a four-screen design in a newsprint editorial style: a front page, a menu-and-slot ordering screen, a checkout, and a staff-side kitchen desk. The product ideas that make this app unusual — capacity ceilings, the payment hold, the cash cap — are surfaced in the UI rather than hidden in the backend.

## About the design files

**The files in `design/` are design references created in HTML.** They are prototypes showing intended look and behavior, not production code to copy.

The target codebase is Django with server-rendered templates. The task is to **recreate these designs as Django templates** using the project's existing patterns — `base.html` plus per-view templates, `{% static %}` for assets, Django forms for the checkout, and whatever the project already uses for light interactivity. Do not port the prototype's React-flavoured structure.

Specifically, do not try to reuse:
- `support.js` and the `<x-dc>` / `{{ hole }}` template syntax — these belong to the design tool, not to Django. Note the collision: `{{ }}` in these files is **not** Django template syntax.
- `_ds/…/_ds_bundle.js` — a compiled runtime for the design tool. The one thing it carries that you do need is the SVG filter defs, which are also supplied standalone as `design-system/print-plates.js`.

What you **should** carry over verbatim: `design-system/styles.css` (all tokens and component classes) and `design-system/print-plates.js`.

## Fidelity

**High-fidelity.** Colors, typography, spacing and interaction states are final and come from a real design system (Broadsheet — its own guide is included as `design-system/readme.md`). Recreate the UI closely. Where this document gives a pixel value, it is the intended value.

Two things are explicitly *not* final: all menu content is sample data pending confirmation with Brandon, and there is only one real photograph.

## Setup in the Django project

1. Copy `design-system/styles.css` to `static/css/broadsheet.css`. It is the only stylesheet — it carries the `:root` tokens, the 100–900 ramps, base type, and the component layer (`.btn`, `.tag`, `.input`, `.radio`/`.dot`, `.table`, `.card`, `.nav`).
2. Copy `design-system/print-plates.js` to `static/js/print-plates.js` and load it beside the stylesheet in `base.html`. It injects the SVG filter defs (`#sep-c`, `#sep-m`, `#sep-y`, `#sep-k`, `#sep-all`) that the `.cmyk` image treatment references. **Without it, every `.cmyk` figure renders as four stacked unfiltered copies of the photo** — a visibly broken hero.
3. **Delete `design/tokens.css`.** It holds the old saffron/maroon palette and will fight the new tokens. See "Open decision" below — confirm the palette change is wanted before doing this.
4. Load Source Serif 4 (weights 300–800, plus true italic at body weight). Self-host it rather than using the Google Fonts CDN — a South African audience on mobile data will feel the difference, and it removes a third-party dependency:
   ```
   font-family: "Source Serif 4", Georgia, serif;
   ```
   Georgia is the fallback; do not fall back to a sans-serif. The serif *is* the UI chrome in this system.
5. Copy `design/assets/hero-dish.jpg` to `static/img/`. It was extracted from the old prototype's inline base64.

## Design tokens

All values below already exist as variables in `styles.css`. Use `var(--*)`; do not hard-code these hexes.

**Color**

| Token | Value | Used for |
| --- | --- | --- |
| `--color-bg` | `#f3f2f2` | Page ground (paper) |
| `--color-surface` | `#eae9e9` | Card fills only |
| `--color-text` | `#201e1d` | Body and headings (near-black ink) |
| `--color-accent` | `#0088b0` | Process cyan — interactive elements |
| `--color-accent-2` | `#d6006c` | Process magenta — rarer second spot |
| `--color-divider` | `#201e1d` at 16% | Hairline rules |
| `--color-process-yellow` | `#edbb00` | Print treatments only — never text or chrome |

Ramps run `--color-neutral-100…900`, `--color-accent-100…900`, `--color-accent-2-100…900`. Key steps used in these screens: `--color-neutral-600` `#7d7979` (fine print), `--color-neutral-700` `#605d5d` (metadata, uppercase labels), `--color-neutral-800` `#444141` (secondary body), `--color-neutral-300` `#d7d3d3` (meter tracks), `--color-accent-700` `#006786` and `--color-accent-2-700` `#aa0b56` (accent at paragraph size).

Accessibility constraint: the base accents hit ~3:1 against the ground — fine for icons, large text and chrome, **not** for body copy. Any accent-colored text at paragraph size must use the 700 step.

**Spacing** — `--space-1` 5px, `-2` 10px, `-3` 15px, `-4` 20px, `-6` 30px, `-8` 40px (a 1.25× density scale — do not tighten it). Larger section gaps in these screens are 56/72/96/110px.

**Radius** — `--radius-sm` 1px, `--radius-md` 2px, `--radius-lg` 4px. Effectively square; this is newsprint, not a SaaS dashboard. Nothing is pill-shaped.

**Shadow** — `--shadow-sm/md/lg`. Barely used here; the design has almost no elevation.

**Type scale as built** (all Source Serif 4):

| Role | Size | Weight | Other |
| --- | --- | --- | --- |
| Masthead | `clamp(52px, 11.2vw, 158px)` | 700 | line-height .9, letter-spacing −.02em |
| Screen title | `clamp(30px, 4vw, 52px)` | 600 | line-height 1, letter-spacing −.015em |
| Hero subhead | `clamp(30px, 3.6vw, 50px)` | 600 | line-height 1.06 |
| Section rubric | 15px | 700 | uppercase, letter-spacing .18em |
| Dish name | 19px | 600 | line-height 1.2 |
| Body | 17px | 400 | line-height 1.55 |
| Lead paragraph | 19px | 400 | line-height 1.6, max 44ch |
| Metadata / eyebrow | 12.5px | 400 | uppercase, letter-spacing .14–.18em, neutral-700 |
| Price | 18–19px | 400 | **italic**, tabular-nums |
| Big figure | 26–34px | 600 | tabular-nums |

Two type rules that carry a lot of the character: every number in the interface uses `font-variant-numeric: tabular-nums`, and every price is set in the serif's **true italic** (never synthesized oblique — load the italic face). Prose blocks use `text-wrap: pretty`.

## Layout rules

- Content column `max-width: 1240px`, `padding: 0 32px`, centred. Checkout narrows to 1000px.
- Flush-left, asymmetric. Headings hug the left edge; whitespace collects on the right. Do not centre headings.
- **Sections are separated by whitespace, not by dividers or cards.** The exceptions in these screens are deliberate newspaper furniture: the 7px solid rule above a dateline rail, the 1px rule below it, and the hairline rules between menu rows and table rows.
- `.card` is not used anywhere. Do not introduce boxes to organise the page.
- Never use both accents inside the same small component.

## Screens

Everything below is one Django view each. The prototype fakes navigation with a tab rail in the header; in production that rail is either real nav links or drops away — the four screens are separate URLs.

---

### 1. Front page (`/`)

Marketing page. Purpose: explain that this is a home kitchen with collection slots, and send the visitor to the menu.

**Header** (sticky, `--color-bg`, 1px bottom divider, `backdrop-filter: saturate(1.1)`): wordmark "Brandon's Kitchen" at 14px/700 uppercase, letter-spacing .14em. Nav items at 14.5px; the active one takes `--color-text` with a 2px `--color-accent-2` bottom border, inactive ones `--color-neutral-600` with a transparent border. Right-aligned cart summary at 13px uppercase tabular-nums, reading either "No order started" or `"3 items · R 285.00"`.

**Dateline rail**: 7px solid `--color-text` bar, then a row of 12.5px uppercase metadata (`Cape Town, South Africa` · date · `Collection only` · `Slots 16:00–18:00` in accent · `Edition No. 1` pushed right), then a 1px rule. The thick-thin pair is front-page furniture and should print at full ink strength.

**Masthead**: "Brandon's Kitchen" at the clamp size above, rendered with `.cmyk-head` — four overlapping copies (`.paper` plus `.plate-c`/`.plate-m`/`.plate-y`) that misregister into a press-plate effect. Fades in over 700ms. In Django, this is four spans with identical text; only the first is readable to screen readers, the other three take `aria-hidden="true"`.

**Hero, two columns** (`1.05fr 0.95fr`, 64px gap, top-aligned):

*Left* — eyebrow "The kitchen" in `--color-accent-2-700`; headline "Roti, curry and Gatsby — cooked to order, from a home kitchen."; lead paragraph (44ch max) explaining collection-only ordering; primary button "View the menu" and secondary "See the kitchen desk", both 46px min-height; then three figures above a 1px top rule — **24** "Orders a day, capped", **15** "Minute collection window", **10:00** "Same-day cut-off". Those three should come from settings, not be hard-coded in the template.

*Right* — the hero photograph in a `.cmyk` figure at `aspect-ratio: 4/3.2`, printed as four separations (the markup is five `<img>` tags of the same source: one visible, four filtered with `.sep-c/-m/-y/-k`). Caption below at 13px: "Plate 1" in accent uppercase, then the descriptive line.

Both hero columns rise-in on load (10px translate, 620/760ms ease-out). Respect `prefers-reduced-motion` — the animations are decorative and should be dropped entirely, not slowed.

**Today's picks**: rubric row with a 1px `--color-text` bottom rule, then three equal columns divided by 1px vertical hairlines (36px inner padding). Each: portion eyebrow in `--color-accent-2-700`, dish name at 25px/600, description at 16px capped to 30ch, italic price. Content: Full House Masala Steak Gatsby (Serves 4, R 130.00), Chicken Masala Roti Roll (Serves 1, R 65.00), Beef Lasagne (Serves 1, R 90.00).

**How collection works**: `0.7fr 2.3fr` grid — heading left, three steps right. Each step leads with a 70px `.cmyk-num` plate numeral (same four-span pattern as the masthead), then a 20px heading and a 30ch paragraph: *Choose your slot* (order for today or the next 7 days, same-day closes 10:00), *We confirm* (EFT or cash; cooking starts on confirmation, not before), *Collect at the door* (15-minute window, text on arrival, no hooting).

**Footer**: 7px top rule, wordmark, location line, "Start an order" ghost button right-aligned, and a 12.5px placeholder-content disclaimer.

---

### 2. Order (`/order/`)

The main ordering screen. `1.6fr 1fr` grid, 72px gap; the menu scrolls, the order panel is `position: sticky; top: 96px`.

**Menu** — five categories, 56px apart. Each category header is a single baseline row: the plate letter in accent-2 italic (34px wide), the category name at 23px/600, a flex-1 hairline filling the gap, then the portion note right-aligned in 12.5px uppercase. Dish rows sit below with a 1px top rule and 48px left indent (aligning under the category name, not the letter):

| Cat | Portion | Dish | Price |
| --- | --- | --- | --- |
| A · Roti & Curry | Serves 1 | Chicken Curry & Roti | R 85.00 |
| | | Steak Curry & Roti | R 95.00 |
| A3 · Masala Roti Rolls | Serves 1 | Chicken Masala Roti Roll | R 65.00 |
| | | Steak Masala Roti Roll | R 70.00 |
| B · Roti & Gatsby, Large | Serves 4 | Chicken Masala Roti & Gatsby | R 110.00 |
| | | Masala Steak Roti & Gatsby | R 115.00 |
| C · Gatsby | Serves 4 | Chicken Masala Gatsby | R 95.00 |
| | | Steak Masala Gatsby | R 100.00 |
| | | Full House Masala Steak Gatsby | R 130.00 |
| D · Italian Lasagne | Serves 1 | Beef Lasagne | R 90.00 |

Descriptions are in the prototype and should be treated as copy to keep verbatim. The Full House row carries a per-dish note field, currently "Portion to confirm" — keep that mechanism; several dishes will need notes.

Each row's right edge holds the quantity control: at qty 0, a single 36px "Add" secondary button. Above 0, it swaps to `− [qty] +` — secondary icon button, tabular-nums count (14px min-width, centred), primary icon button. All three are 36–40px; on mobile these must reach 44px.

**Order panel** — 4px top bar, "Your collection order" rubric, 1px rule. Then:

*Day picker* — 7 chips, one per day from today. Each shows a small uppercase line ("Today", then "Sun", "Mon"…) over a tabular-nums date. Selected: `--color-accent` fill, `--color-bg` text. Unselected: transparent with a `--color-divider` border. 140ms background/color transition.

*Slot picker* — 4-column grid of 15-minute windows, 16:00 through 17:45. Full slots render `--color-neutral-500`, line-through, `cursor: not-allowed`, and are non-clickable. In the prototype, 16:30 and 17:00 are hard-coded full for today only; in production this is a capacity query. Below: "Held for 45 minutes once you place the order." once a slot is picked, otherwise "Two windows are already full for today."

*Order sheet* — one line per item: qty in accent tabular-nums (26px wide), name, line total right-aligned. Empty state: "Nothing on the sheet yet. Add a dish from the menu and it lands here."

*Total* — 1px `--color-text` top rule, "Total" label left, amount right at 30px/600 tabular-nums. Then a block primary button "Continue to payment", disabled until at least one dish **and** a slot are chosen, with a hint below that names the chosen slot and day when ready, or says what's missing when not.

---

### 3. Checkout (`/checkout/`)

Two states in one view.

**Form state** — `1fr 0.9fr` grid, 64px gap. Left: heading "How would you like to pay?", then two radio rows separated by 1px top rules. Use the design system's `.radio` + `.dot` markup, not a bare native radio — the visible marker is the `.dot` span.

- *EFT before cooking* — "Bank details land by SMS. Your slot is held for 45 minutes while the payment clears."
- *Cash on collection* — "Same-day only, and capped — R 180.00 of the day's cash allowance is still open." That figure is live data.

Below, a 1px `--color-text` rule and a two-column field pair: Name ("Who's collecting?") and Mobile ("082 000 0000"), both `.input`, labels 12.5px uppercase `--color-neutral-700`. In Django these become a form; add server-side validation for a SA mobile number, and re-check slot capacity and the cash cap on POST — the client-side disabled state is not a guarantee.

Right column: order sheet (rows divided by hairlines), total at 30px, then collection day and window in 15.5px with the values bolded. Block primary "Place the order", ghost "Back to the menu".

**Confirmed state** — replaces the form. Eyebrow "Order received" in accent-2, then a large heading "We've got it. Collection 17:15." naming the actual slot. Body copy branches on payment method: cash tells them what to bring and that cooking starts on kitchen confirmation; EFT explains the SMS, the 45-minute hold, and that cooking starts on payment verification. Below a 1px rule, three figures 56px apart — Reference, Day, Total — each a 12.5px uppercase label over a 26px/600 value. Then "Start another order" (secondary) and "See it on the kitchen desk" (ghost). Rises in over 520ms.

---

### 4. Kitchen desk (`/kitchen/`)

Staff view. Must be behind auth — it exposes customer names and the day's takings.

Same 7px/1px dateline treatment, reading: `Kitchen desk` · date · `Service 16:00–18:00` in accent · `Run sheet`.

**Three capacity meters**, equal columns, 56px apart. Each is a big tabular-nums figure, a 15px neutral caption, and an 8px bar on a `--color-neutral-300` track:

- **18** "of 24 orders secured" — fill `--color-accent`
- **R 420** "of R 600 cash ceiling" — fill `--color-accent-2`
- **12** "of 20 Gatsby loaves left" — fill `--color-text`

Three different fills is intentional here: they are three unrelated ceilings, and one colour would imply one metric. The bars have no radius.

**Today's run** — a `.table` with columns Slot, Ref, Customer, Items, Pay, Value (right-aligned), Status. Value and slot are tabular-nums; Ref and Items are `--color-neutral-700`.

Status is a `.tag` button that advances through the sequence on click: **Awaiting payment** (`.tag-outline`) → **Confirmed** (`.tag-accent`) → **Cooking** (`.tag-accent-2`) → **Ready** (`.tag-accent`) → **Collected** (`.tag-neutral`), stopping at Collected. In production this is a POST per transition with a real state machine — decide server-side whether backwards moves are permitted, and be aware the prototype allows forward-only. "Cooking" is the one place magenta appears on this screen, because it is the state that matters mid-service.

A closing 12.5px note states that the capacity ceilings, cash cap and payment hold are the product, and that the sheet is the staff-side view of them.

## Interactions & behavior

| Interaction | Behavior |
| --- | --- |
| Add / +/− | Mutates the cart; row control swaps between "Add" and stepper at the 0/1 boundary; order sheet and header summary update |
| Day select | Single-select; re-evaluates which slots are full |
| Slot select | Single-select; full slots inert |
| Continue to payment | Disabled until cart non-empty **and** slot chosen |
| Payment method | Radio; changes the confirmation copy and whether the cash-cap line applies |
| Place the order | Swaps checkout into the confirmed state |
| Status tag | Advances one step, clamped at Collected |
| Load | Hero columns and the confirmation rise in (10px, 520–760ms ease-out); masthead fades (700ms) |
| Chips | 140ms background/color transition |

All hover, pressed, focus and disabled states ship inside `styles.css` — hovers and pressed states come off the accent ramp, focus is a 2px accent `:focus-visible` ring at 2px offset, disabled drops to 45% opacity. **Do not restyle them per template**, and do not let the browser default blue focus ring through.

Not yet designed, and needed before launch: loading states, server-error states, the sold-out-while-you-were-deciding race, and the responsive breakpoints. Every grid in these screens is a fixed multi-column layout that will need to collapse to one column on mobile — the order panel in particular should probably become a sticky bottom bar. Worth a design pass rather than a developer guess.

## State

Prototype state, and roughly what production needs:

- `cart` — map of dish id → qty. Session, or a draft Order row.
- `day` (index 0–6) and `slot` (time string or null) — the chosen collection window. Must be validated against live capacity on submit.
- `pay` — `"eft"` or `"cash"`. Cash is same-day only and subject to the daily ceiling.
- `name`, `phone` — customer details.
- `confirmed` — a UI flag in the prototype; in production, order creation.
- `orders[].si` — status index per order on the kitchen desk; a real state field.

Data the prototype hard-codes that must come from the backend: the dish list and prices, slot availability per day, the cash allowance remaining, all three capacity meters, the order reference, and the run sheet.

## Assets

- `design/assets/hero-dish.jpg` — masala steak Gatsby. The only real photograph; extracted from the previous prototype's inline base64. It appears five times in the hero markup (one visible plus four filtered separations) — serve it once and let the browser cache it.
- No other imagery. The menu is deliberately text-only, and the front page has no secondary photography. If dish photos arrive, the front page needs re-balancing rather than dropping images into the existing grid.
- Icons: none used. If any are needed later, the system specifies Phosphor duotone.

## Files in this bundle

```
design/
  Brandon's Kitchen.dc.html   All four screens — the design reference
  assets/hero-dish.jpg        The hero photograph
  support.js, _ds/            Design-tool runtime — needed only to open the
                              reference in a browser; do not port
design-system/
  styles.css                  Port this — all tokens and component classes
  print-plates.js             Port this — the .cmyk SVG filter defs
  readme.md                   The Broadsheet design system's own guide
screens/
  01-screen.png               Front page
  02-screen.png               Order — cart populated, 17:15 selected
  03-screen.png               Checkout — form state
  04-screen.png               Kitchen desk
```

The screenshots are above-the-fold captures at ~910px wide, for orientation only. They do not show the full scroll of any screen, and at that width the layout is already compressing — open the HTML for the real thing.

Open `design/Brandon's Kitchen.dc.html` directly in a browser to click through all four screens.

## Open decision before you start

This design drops the saffron/maroon palette in `design/tokens.css` for Broadsheet's process cyan and magenta on paper white. That has not been signed off. Retheming is cheap now and expensive once the markup is split across a dozen templates, so confirm the palette before building. If the old brand colors must stay, the layout, type scale and print treatments all survive a palette swap — the tokens at the top of `styles.css` are the only place that needs to change.
