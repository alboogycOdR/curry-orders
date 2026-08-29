# Templates

`base.html` is the shared page shell for the Broadsheet design system —
header/nav chrome plus the Django block structure (`{% block title %}`,
`{% block extra_head %}`, `{% block content %}`) every screen extends.

## The four handoff screens are built

- Front page (`/`) — `public/home.html`
- Order (`/order/`) — `public/order.html`
- Checkout (`/checkout/`) — `public/checkout.html`
- Kitchen desk (`/manage/kitchen/`, staff-only) — `staff/kitchen.html`

Each recreates its screen from the design handoff at
`updates/Curry orders modernization/design_handoff_brandons_kitchen/README.md`
against real (if still placeholder-data) Django views — see
`public/views.py` and `staff/views.py`'s module docstrings for exactly what
is and isn't wired to real data yet, and `docs/DECISIONS.md` D-32 for why
these are four routes, not the five spec §6.1 lists for the customer site.

Two things worth knowing before touching any of the four:

- **The cart is client-side.** `static/js/cart.js` holds it in
  `localStorage`, not a session or a database row — there is no
  `core.capacity`/order-creation code yet (milestones 2-3). Every page
  that reads or writes the cart goes through `window.BKCart`; don't add a
  second cart representation.
- **The kitchen desk has no auth.** It should — the handoff says so
  explicitly (customer names, the day's takings) — but staff auth doesn't
  exist yet either. See `staff/views.py`'s module docstring before
  deploying this route anywhere reachable.

## Nav URLs are real

`base.html`'s header nav uses `{% url %}` against `public:home`,
`public:order`, `public:checkout`, `manage:kitchen` — all four resolve
(`config/urls.py`, `public/urls.py`, `staff/urls.py`).

## Still open

- **Responsive/mobile breakpoints** are a minimal single-column fallback
  in each screen's own `<style>` block, not the real design pass the
  handoff explicitly defers ("worth a design pass rather than a developer
  guess"). Revisit before shipping any of this beyond internal review.
- **Server-side validation** — the handoff calls this out for checkout
  specifically (SA mobile number format, slot capacity, cash cap must all
  be re-checked on POST, not just gated client-side) — doesn't apply yet
  because checkout doesn't POST anywhere real yet (milestone 3).
- Real menu/dish content, slot capacity, the cash cap and the kitchen run
  sheet are all sample data pending the owner inputs in spec §23 and the
  milestones that build the queries behind them (see the per-view comments
  in `public/views.py`/`staff/views.py` for exactly which milestone owns
  which number).
