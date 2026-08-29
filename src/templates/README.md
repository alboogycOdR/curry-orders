# Templates — handoff note

This directory currently holds only `base.html`, the shared page shell for
the Broadsheet design system. It is **not** a finished screen — it's the
header/nav chrome plus the Django block structure (`{% block title %}`,
`{% block extra_head %}`, `{% block content %}`) that the four real screen
templates will extend.

## What still needs building

The four screens from the design handoff are not built yet — that's a
later pass, against the models the core-app agent is building concurrently:

- Front page (`/`)
- Order (`/order/`)
- Checkout (`/checkout/`)
- Kitchen desk (`/kitchen/`, staff-only)

Each should be a template that starts `{% extends "base.html" %}` and fills
in `{% block content %}` per its own section of the spec. The full spec —
layout grids, exact spacing, copy, interaction behavior, the `.cmyk`
photograph treatment, the day/slot pickers, the status-tag state machine,
etc. — is at:

`updates/Curry orders modernization/design_handoff_brandons_kitchen/README.md`

Read that in full before starting a screen template; it also links out to
`design-system/readme.md` (the Broadsheet system's own component guide) and
the four reference screenshots under `screens/`.

## Nav URLs are plain hrefs for now

`base.html`'s header links to `/`, `/order/`, `/checkout/`, `/kitchen/` as
plain `href` attributes, not `{% url %}` tags — `src/config/urls.py` (and
the per-app `urls.py` files) don't exist yet as of this pass, and `{% url %}`
would raise `NoReverseMatch` and hard-fail the render before they do.

Once the URLconf exists, each link should become a real `{% url %}` call
against these placeholder names (already noted inline as TODO comments next
to each link in `base.html`):

| Screen | Placeholder URL name |
| --- | --- |
| Front page | `public:home` |
| Order | `public:order` |
| Checkout | `public:checkout` |
| Kitchen desk | `manage:kitchen` |

The active-link state (`aria-current="page"` plus the accent-2 underline)
is already wired to `request.resolver_match.url_name`, so it should keep
working unchanged once the hrefs are swapped for `{% url %}` — just make
sure the URL names you register match the ones above (or update both
places together).

## Other things a screen template will need that base.html doesn't provide

`base.html` is deliberately narrow — just the header/nav shell. It does
**not** include the dateline rail, the masthead, the hero, or any other
per-screen furniture described in the handoff. Each screen template owns
all of that inside its own `{% block content %}`.

A few things worth flagging for whoever builds the screens next:

- `cart_summary` is a plain template variable (`{{ cart_summary|default:"No
  order started" }}` in the header), not wired to real cart state. Views
  will need to pass it in, or a context processor will need to compute it.
- The three front-page hero figures (24 orders/day, 15-minute window, 10:00
  cut-off) should come from settings per the handoff, not be hard-coded.
- Client-side disabled states (continue-to-payment, full slots, etc.) are
  not a substitute for server-side validation — the handoff calls this out
  explicitly for checkout (SA mobile number format, slot capacity, cash cap
  must all be re-checked on POST).
- Responsive/mobile breakpoints are explicitly **not** designed yet per the
  handoff's "Interactions & behavior" section — treat that as a follow-up
  design pass, not a developer guess, before shipping any screen.
