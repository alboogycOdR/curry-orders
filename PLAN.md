# Roti Connect wireframe build — live status

Source of truth for **what is done**. Design detail lives in
[`docs/ROTI_CONNECT_WIREFRAME_PLAN.md`](docs/ROTI_CONNECT_WIREFRAME_PLAN.md).
Screen copy/wireframes: [`docs/_wireframe_spec_extract.md`](docs/_wireframe_spec_extract.md).

**Any agent:** implement the next `in_progress` / first `todo` task, then
set its **Status** to `done` and tick every work item. Do not skip ahead
past an unfinished dependency. Do not implement OTP, `RC-` order numbers,
or remove the `/order/` slot picker before Task 5.

Status values: `todo` · `in_progress` · `done` · `blocked`

---

## Legend

| Field | Meaning |
|---|---|
| Task | One PR from the design plan |
| Status | Whole-task rollup |
| Work items | Atomic checkboxes; mark `[x]` when that item is merged/verified |

---

## Task 1 — PR 1: Roti Connect chrome, titles, public tokens

- **Status:** done
- **Depends on:** none
- **Verify:** `py -3 -m pytest tests/integration/test_screens.py tests/integration/test_help_and_policies.py tests/integration/test_staff_auth_views.py -q`
- **Browser:** `/` `/order/` `/help/` `/account/` `/lookup/` `/checkout/`

### Work items

- [x] Rename every public `{% block title %}` to Roti Connect
- [x] Help intro: kill “at Brandon's Kitchen”
- [x] Share titles (`checkout.js`, `order_status.html`) → Roti Connect
- [x] Home prototype footer: no “finalised with Brandon”
- [x] Menu tab → `public:order` (`/order/`); Basket tab stays `public:checkout`
- [x] Do **not** add `/basket/` or D-35
- [x] `body.route-public` tokens (KD-1): ink/muted/pink/teal/paper/surface, radius 16/999/12, `--font-ui`
- [x] Selected tab uses pink `#9B1B4A`; page `padding-bottom ≥ 72px`; tab bar 56px + safe area
- [x] `seed_dev` `public_site_name` → Roti Connect
- [x] Tests: `TestHome` no longer requires `b"Brandon"`; Menu href is `public:order`; staff settings POSTs that save “Brandon's Kitchen” stay
- [x] No public screen shows Brandon's Kitchen; staff templates untouched

---

## Task 2 — PR 2: Home — category tiles, hero, live prices

- **Status:** done
- **Depends on:** Task 1
- **Verify:** `py -3 -m pytest tests/integration/test_screens.py tests/unit/test_storage_service.py -q`
- **Browser:** `/` at 390px

### Work items

- [x] Single mobile-app column (KD-11); drop dual desktop magazine as primary
- [x] Remove Home search
- [x] Collection chip (Kraaifontein, window, cut-off — no street)
- [x] `storage.service.public_dish_image_url` (CDN → S3 public → `/media/{key}`)
- [x] DEBUG serve `MEDIA_ROOT`; `MenuDish.photo_url`; `onerror` placeholder (no MinIO HEAD)
- [x] Featured = `?featured=` else `chicken-masala-roti-roll` if active else first active
- [x] Hero: photo, name, `price_cents`, CTA **under** photo → `/order/?featured=<slug>`
- [x] 2×2 category tiles (KD-9 chip map, from-price, ≥44px) → `/order/#roti` etc.
- [x] How-it-works 3 steps + link `/help/`; Find my order → `/lookup/`
- [x] Cut-off-passed copy; sold-out edition via occupying count (**not** `check_day_cap`)
- [x] No empty colour tiles

---

## Task 3 — PR 3: Menu cards, sticky chips (keep slots)

- **Status:** done
- **Depends on:** Task 2
- **Verify:** `py -3 -m pytest tests/integration/test_screens.py tests/integration/test_menu.py -q`
- **Browser:** `/order/` `/order/#gatsby`

### Work items

- [x] Photo cards 72×72, name, one-line, `portion_label` on the item, price, 44px `+`
- [x] Sticky chips All / This week / Roti / Gatsby / Curry / Lasagne (KD-9)
- [x] Section ids `section-gatsby` etc.; hash `scrollIntoView`
- [x] Dual-category dishes in both named sections; All / This week unique by `dish.id`
- [x] Remove sample banner (`?preview=1` only)
- [x] Sold-out: 40% photo, badge, `+` disabled
- [x] **Keep** day/slot picker on `/order/` until Task 5
- [x] Hide R0.00 footer when cart empty; sticky bar href stays `/checkout/`

---

## Task 4 — PR 4: Item sheet overlay + cart v2

- **Status:** done
- **Depends on:** Task 3
- **Verify:** `py -3 -m pytest tests/integration/test_checkout_api.py tests/integration/test_reorder.py tests/integration/test_screens.py tests/integration/test_seed_dev.py tests/unit/test_ordering.py -q`
- **Browser:** `/order/` open sheet, change extras, add, sticky bar

### Work items

- [x] `_item_sheet.html` + `item-sheet.js` bottom sheet; hide tab bar while open
- [x] `#menu-data` via `_menu_catalog_payload` (options + `photo_url`)
- [x] DB group stays **Spice**; sheet copy **Heat**; default Medium
- [x] Seed Spice on roti/gatsby/curry; Extra roti +1200 / Chips −500 only on chip dishes; Full House still one required group
- [x] Cart v2 in `rc_cart_v2` only: `getLines` / `upsertLine` / `updateLine` / `totals`; remove map `getCart`/`setCart`/`setLine`/`bump`/`getDay`/`setDay`
- [x] Migrate `bk_cart_v1` on read; persist `dayIso`
- [x] Port `order.js` + `checkout.js` off `getDay()` index onto `getDayIso()`
- [x] `cartToLines` sends `kitchen_note`; reorder writes v2 via `setState`
- [x] `+` and whole row open sheet; toast Added; no auto-jump to basket
- [x] Go-live sheet note: production needs Spice/extras/photos
- [x] POST `/api/checkout` still `{dish_id, option_value_ids, kitchen_note}` after v1→v2

---

## Task 5 — PR 5: `/basket/` — steppers, day + slot, empty state

- **Status:** todo
- **Depends on:** Task 4
- **Verify:** `py -3 -m pytest tests/integration/test_screens.py tests/integration/test_checkout_api.py tests/integration/test_availability_api.py tests/integration/test_security_headers.py -q`
- **Browser:** add item → `/basket/` pick FULL vs open slot → Edit sheet → Continue

### Work items

- [ ] New `public:basket` at `/basket/` (not `/cart/`)
- [ ] Move day chips + slot grid + line steppers + Continue off `/order/`
- [ ] Day chips use `getDayIso`/`setDayIso`
- [ ] Host item sheet on basket; Edit = `BKCart.updateLine` (not navigate to `/order/`)
- [ ] `views.basket` emits same `#menu-data`; missing/sold-out disables Edit
- [ ] **No** `GET /api/menu`
- [ ] `GET /api/availability?date=` frozen JSON (remaining/FULL, cash, dishes, `day_remaining`); 400 `outside_horizon`; never `check_day_cap`
- [ ] Continue disabled until cart + live slot; empty state has no Total R0.00 / Place order
- [ ] Reorder lands here with slot unselected
- [ ] Retarget Basket tab, desktop bag, sticky bar to `/basket/`
- [ ] `Disallow: /basket/` in robots.txt
- [ ] Delete slot/day UI from `order.html`
- [ ] Record **D-35 once** in `docs/DECISIONS.md`

---

## Task 6 — PR 6: Checkout — fulfilment first, no empty Collect

- **Status:** todo
- **Depends on:** Task 5
- **Verify:** `py -3 -m pytest tests/integration/test_checkout_api.py tests/integration/test_screens.py -q`
- **Browser:** `/checkout/` with and without a slot; place EFT against seed

### Work items

- [ ] Redirect to `/basket/` if cart empty or no `slotId` (never Collect —)
- [ ] Layout: Collect summary + Change slot → `/basket/`, then name/phone, then EFT/cash, then lines, Place order
- [ ] EFT 30-min hold visible on this screen
- [ ] Cash only when `dayIso === today` and cash remaining and cash enabled
- [ ] On 201 go to `/orders/<public_token>/`; on `slot_full` return to Basket with toast
- [ ] Keep policies checkbox; `kitchen_note` already from Task 4

---

## Task 7 — PR 7: Tracker steps + Find my order

- **Status:** todo
- **Depends on:** Task 6
- **Verify:** `py -3 -m pytest tests/integration/test_lookup.py tests/integration/test_order_status_eft_panel.py tests/unit/test_lookup.py tests/integration/test_screens.py -q`
- **Browser:** place order → tracker; `/lookup/` known pair and bad pair

### Work items

- [ ] `public/status_ui.py` five dots; later dots stay filled; terminals replace stepper
- [ ] Replace `_STATUS_COPY` (do not layer)
- [ ] Hold-lapsed `payment_review` stays Held with distinct copy (D-09)
- [ ] Optional 30s meta refresh on non-terminal
- [ ] Show `CT-YYMMDD-NNNN` (Copy); lookup placeholder `CT-260901-0001`
- [ ] Canonicalise `^[Cc][Tt]-?\d{6}-?\d{4}$` in `normalize_order_number`; refuse `RC-1847`
- [ ] I've paid = existing proof upload (file required)
- [ ] Tracker keeps the tab bar; generic lookup failure (no enumeration)

---

## Task 8 — PR 8: Account + Repeat (password v1, not OTP)

- **Status:** todo
- **Depends on:** Task 7
- **Verify:** `py -3 -m pytest tests/integration/test_customer_auth.py tests/integration/test_reorder.py tests/integration/test_screens.py -q`
- **Browser:** `/account/`, login, Repeat

### Work items

- [ ] **No** SMS OTP / Send code chrome
- [ ] Fix account-takeover: `customer_signup` must refuse to set a password on a row that already has one **even if `password_hash` is currently NULL** — a guest Customer row created at checkout has `password_hash=NULL`; today's code treats that as "no account", letting anyone who knows the mobile number claim it. Guard: `get_or_create` then check `password_hash` **and** whether the row pre-existed (via `created`); if the row already existed (`created=False`) and has no password yet, require OTP or a dedicated "claim account" flow (v1: reject with "An account may already be linked to this number — contact us.") rather than silently setting a password on a stranger's order history.
- [ ] Logged-out: mobile + password + Log in / Sign up + guest lookup
- [ ] Logged-in: Hi {name}, last collected order, Repeat → `/basket/` slot unselected
- [ ] Home Repeat module when history exists
- [ ] Persist `rc_last_order_v1` on checkout for guest
- [ ] Guest checkout remains ungated

---

## Task 9 — PR 9: Help as four cards; one-liners on Home and Checkout

- **Status:** todo
- **Depends on:** Task 2, Task 6
- **Verify:** `py -3 -m pytest tests/integration/test_help_and_policies.py tests/integration/test_screens.py -q`
- **Browser:** `/help/` `/` `/checkout/`

### Work items

- [ ] Four cards with live Settings figures (cut-off, slots, cook-after-EFT, Kraaifontein)
- [ ] No Brandon's Kitchen; policies + WhatsApp links
- [ ] Shared one-liners partial on Home and Checkout

---

## Do not touch

- `src/core/capacity.py`, `src/core/transitions.py`
- Staff templates and staff JS
- `deploy/`, `docker-compose.yml`, secrets
- `schema_v1_1.sql` / `core/migrations/`
- Historical `design/prototype/` and `updates/`

---

## Definition of done (spec §13)

- Guest: Home → featured roti → configure Medium → add → pick a slot → name/phone → place EFT → see `CT-YYMMDD-NNNN`
- Second device recovers via Find my order
- After 10:00, Today is not offered
- A FULL slot cannot be selected
- No screen shows Brandon's Kitchen
- No empty colour tiles on Home
