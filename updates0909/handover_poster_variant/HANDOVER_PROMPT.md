# Handover prompt

Paste this as your first message in the Claude Code session, with this folder available in the working directory.

---

I'm handing you a design handover for the Roti Connect customer site. The repo is this one — Django, Postgres, server-rendered templates, self-hosted. The customer surface already exists under `src/templates/public/` in a light editorial style. We are replacing that surface with a new "poster variant" derived from the client's own promotional flyer.

Before writing any code, read these three, in order:

1. `handover_poster_variant/README.md` — what was built, what it replaces, and the open questions.
2. `handover_poster_variant/Roti Connect Poster Variant - Design & Style Guide.md` — the specification. This is the source of truth. Where it and the README disagree, the style guide wins.
3. `handover_poster_variant/design/Roti Connect — mobile flow (poster).dc.html` — the design reference. Read the source for exact values; it also opens in a browser if you want to see it.

Then come back to me with:

- Your understanding of the scope, in your own words.
- Answers you need from me on the six open questions in the README — especially whether we keep the current URLs or move to the guide's single-page architecture, since that decides how the templates get split.
- A build plan broken into reviewable chunks.

Do not start implementing until we've agreed the plan.

## Constraints

- **The design reference is a reference, not code.** It was authored in a design tool. Do not port `support.js`, the `<x-dc>` wrapper, the `{{ }}` template holes (they are not Django syntax — watch that collision), or the `.pv-phone` phone mock. Recreate the design as Django templates using this project's existing patterns.
- **No CDNs and no frameworks.** CSP `script-src` is `'self'` only — see `config/security_headers.py`. Self-host Barlow Condensed. Plain JS, matching what the repo already does.
- **Staff templates are out of scope.** Only `body.route-public` retokens. `:root` stays as it is. Check nothing the staff boards use depends on the values you're changing.
- **Tokens, not hexes.** Every colour, shadow, radius and easing comes from a variable. The style guide is explicit about this.
- **No fake states.** Until checkout, order lookup and proof upload are genuinely wired, show visible placeholder notices. No invented order numbers, no confirmation of a payment that didn't happen, no claim that a slot is held unless the backend actually held it. The repo already has a real `POST /api/checkout` and an order-status page — reuse them rather than rebuilding.
- **Promotion content is data, not markup.** The featured dish, price, date, deadline, available-from time, location and phone number must all be configurable. Do not bake this Friday into a template.
- **Keep it accessible.** 44px touch targets, semantic heading order, accessible names on icon-only buttons, Escape closing overlays, focus managed in the drawer and modal, and a visible gold-or-blue focus ring — the UA default is invisible on navy and there's no stylesheet to inherit one from.

## Where to be careful

- The reference is mobile only. Tablet and desktop are specified in the style guide (§10.1, §10.5) but not designed. Flag it rather than guessing.
- The order status page in the repo is fully built and has not been restyled. It needs to be.
- The images in `design/assets/poster/` are crops I made from the flyer. They are interim. Never render the full flyer — its baked-in text duplicates the live HTML.
- The flyer and the style guide give different phone numbers. Ask me before shipping either.
