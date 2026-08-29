# Templates

`base.html` is the shared page shell for the Broadsheet design system —
header/nav chrome plus the Django block structure (`{% block title %}`,
`{% block extra_head %}`, `{% block content %}`) every screen extends.

## The four handoff screens are built, plus the real menu/dish pages

- Front page (`/`) — `public/home.html`
- Order (`/order/`) — `public/order.html`
- Checkout (`/checkout/`) — `public/checkout.html`
- Kitchen desk (`/manage/kitchen/`, staff-only) — `staff/kitchen.html`
- Menu (`/menu/`) and Dish detail (`/dishes/:slug/`) — spec §11.3/§11.4,
  not part of the four-screen handoff (D-32) — `public/menu.html`,
  `public/dish_detail.html`

Each recreates its screen from the design handoff at
`updates/Curry orders modernization/design_handoff_brandons_kitchen/README.md`
(the menu/dish pages have no handoff mock — styled from the same design
system tokens) against real Django views — see `public/views.py` and
`staff/views.py`'s module docstrings for exactly what is and isn't wired
to real data yet, and `docs/DECISIONS.md` D-32 for why the customer site
is these five routes, not the five spec §6.1 itself lists (`/menu`,
`/dishes/:slug`, `/cart`, `/checkout`, `/orders/:public_token` — close,
but `/cart` doesn't exist as its own route; that's still folded into
`/order/`).

Milestone 2 (menu/dish/availability) is real: `core.menu` queries
`core.Dish`/`core.DayDishAvailability` directly, sold-out state included.
Milestone 3 (capacity engine, checkout, order creation) is **written but
not wired to any view** — `core/capacity.py`'s `reserve()` and
`core/ordering.py` exist and are tested (including a real concurrency
race test), but nothing calls them yet. Two things worth knowing before
touching any of the five pages:

- **The cart is still client-side.** `static/js/cart.js` holds it in
  `localStorage`, not a session or a database row. Every price a cart
  line carries is **integer cents** (`core.Dish.price_cents` /
  `DishOptionValue.price_delta_cents`), matching how the backend stores
  money everywhere (`core/money.py`) — `cart.js`'s own `rands()`
  formatter mirrors `core.money.format_cents` exactly (space-thousands,
  two decimals) for that reason. Every page that reads or writes the
  cart goes through `window.BKCart`; don't add a second cart
  representation, and don't pass a rand-scale number into it.
- **The kitchen desk is auth-gated** (`@staff_login_required`,
  `staff/decorators.py`) — see `staff/sessions.py` and
  `docs/DECISIONS.md` D-33 for the custom session mechanism behind it
  (`core.User` isn't wired to `django.contrib.auth`). Log in at
  `/manage/login/`; `manage.py seed_dev` creates dev accounts and a
  placeholder dish catalogue.

## Nav URLs are real

`base.html`'s header nav uses `{% url %}` against `public:home`,
`public:order`, `public:checkout`, `manage:kitchen` — all four resolve
(`config/urls.py`, `public/urls.py`, `staff/urls.py`). `public:menu` and
`public:dish_detail` exist too but aren't in the header nav — reached via
the "View the menu" CTA (home) and menu-card links.

## Still open

- **Responsive/mobile breakpoints** are a minimal single-column fallback
  in each screen's own `<style>` block, not the real design pass the
  handoff explicitly defers ("worth a design pass rather than a developer
  guess"). Revisit before shipping any of this beyond internal review.
- **Server-side validation** — the handoff calls this out for checkout
  specifically (SA mobile number format, slot capacity, cash cap must all
  be re-checked on POST, not just gated client-side) — doesn't apply yet
  because checkout doesn't POST anywhere real yet (milestone 3: wire
  `core.capacity.reserve()` to an actual view).
- The order screen's slot list only ever looks at the *soonest* orderable
  day (see `public/views.py`'s `_slot_list_for_day` docstring) — picking
  a different day doesn't re-fetch slots yet. Real per-date re-validation
  needs `GET /api/availability?date=`, milestone 3 surface area.
- The kitchen run sheet and its capacity meters are still sample data —
  see `staff/views.py`'s module docstring for which milestone (6) owns
  the real aggregate queries.
