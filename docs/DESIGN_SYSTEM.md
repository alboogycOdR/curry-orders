# Design system — placeholder theme

**Status: placeholder.** Direction chosen 2026-08-29; swaps for the owner's
real logo and brand colours once §23 lands ("Outstanding" as of this
writing). Tokens live in [`design/tokens.css`](../design/tokens.css) —
change the palette there, not inline in templates, so the swap is a
one-file edit later.

## Where this came from

Surveyed a Magnific gallery of "Indian restaurant landing page" designs
(AI-generated stock imagery/mockups, not real coded templates) via
`browser-use` on 2026-08-29. Two directions were visible across the grid:
a dark, jewel-tone, photography-driven style (near-black or deep
maroon/purple backgrounds, saturated saffron/magenta/emerald accents,
overhead thali-spread food photography, mandala/paisley/lantern motifs
used as borders or corner accents) and a lighter illustrated/flat-vector
style. **Dark jewel-tone was chosen.**

## Colour

All pairings below are checked against `--color-bg` (#140d0b) using the
WCAG relative-luminance formula, because spec §16 requires WCAG 2.1 AA and
several of the source gallery designs would not clear it as built (light
text on mid-saturation photography, thin strokes, etc.) — copy the mood,
not the literal contrast choices.

| Token | Hex | Role | Contrast on `--color-bg` | AA normal text (≥4.5:1)? |
|---|---|---|---|---|
| `--color-bg` | `#140d0b` | Page background | — | — |
| `--color-surface` | `#2a1714` | Cards, panels | — | — |
| `--color-text` | `#f5eae0` | Primary text | 16.2:1 | Yes |
| `--color-text-muted` | `#c9b8ac` | Secondary text | 10.0:1 | Yes |
| `--color-saffron` | `#e8930a` | Primary CTA, links, accents | 7.9:1 | Yes |
| `--color-success` | `#2e9370` | Status: confirmed/ready | 5.1:1 | Yes |
| `--color-danger` | `#e85a5a` | Status: expired/cancelled | 5.5:1 | Yes |
| `--color-warning` | `#e8930a` (=saffron) | Status: hold lapsed / SLA breached | 7.9:1 | Yes |
| `--color-magenta` | `#c6296b` | Rare accent (promo tags) | 3.6:1 | **No — large text/UI components only (≥3:1)**, never body text |
| `--color-maroon` | `#7a1e2b` | Decorative: borders, motif strokes, secondary button outline | not used as text | n/a |
| `--color-gold-line` | `#d9a648` | Decorative: thin line-art dividers only, deliberately muted vs. saffron so it doesn't compete as a second CTA colour | not used as text | n/a |

**Button/badge rule, already verified so it doesn't need rechecking per
component:** every saturated fill above (`saffron`, `success`, `danger`,
`warning`) pairs with `--color-bg` as the foreground text/icon colour —
that is the ratio already measured, in both directions (contrast ratio is
symmetric). **Do not** put `--color-text` (near-white) on these fills
without rechecking: white-on-saffron measures ≈2.4:1 and fails AA even at
large-text size.

## Typography

- **Display** — [Fraunces](https://fonts.google.com/specimen/Fraunces)
  (variable serif). Carries the warm, expressive personality the source
  gallery got from script/hand-lettered headlines, without the small-size
  legibility problems a real script font causes — WCAG 2.1 AA is a hard
  requirement here (§16), so cursive stays out of running text entirely.
  Italic weight used sparingly for a secondary display line (see preview).
- **Body / UI** — [Inter](https://fonts.google.com/specimen/Inter). Same
  family for public site, staff dashboard, forms — one legible, well-
  hinted sans for everything that isn't a headline.
- Loaded from Google Fonts in the preview file for speed of iteration;
  milestone 2 should self-host the two variable `.woff2` files instead
  (matches the "own the whole stack" reasoning behind D-13/D-28, and
  removes a third-party render-blocking request from the §11.1 LCP
  budget).

## Motif use

Mandala/paisley/lantern ornament shows up constantly in the source
gallery, but always as a **contained accent** (a card border, a corner
flourish), never as a full-viewport repeating texture. Follow that:

- Single-line SVG, `stroke: var(--color-gold-line)`, low opacity
  (~15–25%) — see the `.divider` gradient rule in `design/preview.html`
  for the cheapest version of this (a CSS gradient line, not an image at
  all).
- Never a raster/PNG background texture — costs paint and page weight for
  no readability gain, and works against the §11.1 budget (LCP < 2.5s,
  total JS < 60kB) doubly so once §17.6's Helsinki latency is added on
  top.
- Real dish photography (once it exists) is the hero image; ornament
  stays secondary. This is a home kitchen, not a restaurant chain — avoid
  any treatment (glossy composites, heavy vignettes) that visually
  overstates the scale of the operation. Stock "restaurant" photography
  gets replaced by real dish photos before go-live, not layered under
  them.

## Verifying the tokens

`design/tokens.css` is plain `:root { --color-*: ...; }` — valid CSS
everywhere, no build step, so `design/preview.html` renders it directly
in any browser today. That's deliberate: Tailwind v4's `@theme { ... }`
block (below) is a **build-time-only** directive the Tailwind compiler
consumes — a browser loading it unprocessed does nothing with it, so it
is not shipped as a second, unverifiable "source of truth" file.

## Wiring into Tailwind v4 (milestone 2)

```css
/* app entry stylesheet */
@import "tailwindcss";
@import "./tokens.css"; /* keeps design/tokens.css as the single source */

@theme {
  --color-bg: var(--color-bg);
  --color-surface: var(--color-surface);
  --color-saffron: var(--color-saffron);
  --color-maroon: var(--color-maroon);
  --color-gold-line: var(--color-gold-line);
  --color-magenta: var(--color-magenta);
  --color-success: var(--color-success);
  --color-danger: var(--color-danger);
  --color-warning: var(--color-warning);
  --font-display: var(--font-display);
  --font-body: var(--font-body);
}
```

This makes `bg-saffron`, `text-success`, `font-display`, etc. available as
ordinary Tailwind utilities while `design/tokens.css` stays the one file
to edit for the real-brand swap.
