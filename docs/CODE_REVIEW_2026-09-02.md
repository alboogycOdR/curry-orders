# Ultra Code Review — Customer-Facing App — 2026-09-02

Adversarial audit of the customer-facing Django app (`src/public/`, `src/static/js/`, `src/templates/public/`), run via `/code-review ultra`. Scope excluded `src/core/capacity.py`, `src/core/transitions.py`, staff templates, `deploy/`, `docker-compose.yml`, and migrations. No code was changed as part of this review.

Findings are ranked most-severe first. Each was independently verified against the code, not just the finder's claim.

## Critical — data exposure

### 1. Mobile-only lookup leaks any customer's orders
**File:** `src/public/views.py:698` (plus `src/core/lookup.py`, `last9_digits`)

The mobile-only `/lookup/` path returns any phone number's 5 most recent orders — including public-token links and 24h auth cookies — with zero ownership verification. `core.lookup.last9_digits` accepts 1–8 digit fragments, so a suffix like `7` matches every order ending in 7.

**Repro:** POST `/lookup/` with `order_number=''` and `mobile='0821234567'` (or just `'567'`) → page lists a stranger's orders, names, totals, and collection days, each linked to `/orders/<public_token>/`, which `order_status()` serves to anyone. Only a 10/hour/IP throttle guards this. The page's docstring promise ("cannot ... confirm a mobile") is false.

**Fix:** Require order number for guests, or restrict mobile-only listing to `request.customer_user`'s own mobile. Make `last9_digits` require exactly 9 digits.

### 2. Path traversal in public media proxy can reach private proof-of-payment bucket
**File:** `src/public/views.py:998`

`public_media` accepts `<path:key>` and only checks `key.startswith('dish-images/')`, then fetches `f'{endpoint}/{bucket}/{key}'` via urllib (follows redirects). A key like `dish-images/../../curry-proofs/<proof-key>` can be normalised by the object store's router into the private proofs bucket.

**Repro:** GET `/media/dish-images/../../curry-proofs/2026/09/abc.jpg` → Django decodes and passes the path through; MinIO/gorilla-mux path cleaning resolves the `..` → customer proof-of-payment (bank details) served publicly with `Cache-Control: public`.

**Fix:** Reject any `..` segment / normalise with `posixpath.normpath` and re-check the prefix.

## High — broken customer journeys

### 3. Reorder never works
**File:** `src/templates/public/reorder.html:55`

Inline script calls `window.BKCart.setState(...)` during parse, but `cart.js` is loaded with `defer` (`base.html:9`), so `BKCart` is undefined; the `TypeError` is swallowed by the try/catch and the cart is never seeded.

**Repro:** Collected order → "Order these again" → `/orders/<token>/reorder/` renders the summary, customer clicks "Choose a date & slot" → `/basket/` shows the empty-basket state. Every reorder silently fails.

**Fix:** Wrap in `DOMContentLoaded` or move to a deferred script.

### 4. Capacity error recovery is built for the wrong response shape
**File:** `src/static/js/checkout.js:181`

`slot_full` handling expects `body.alternatives` as an array of `{id, label}`, but `reserve()` returns `{slots: [{slot_id, label, remaining}]}` (`capacity.py:276-285`). `day_full` reads `body.next_open_date`, which `_next_open_date_alternative()` never emits (returns `{}`).

**Repro:** Slot fills between basket and Place Order → 422 `slot_full` → `Array.isArray(alternatives)` is false → no alternative buttons, only the message. Day cap hit → "The next available day is Invalid Date." (`new Date('undefinedT00:00:00')`).

**Fix:** Read `body.alternatives.slots[].slot_id`, and drop/guard the `next_open_date` copy.

### 5. Change-time panel shows full slots as selectable
**File:** `src/static/js/checkout.js:601`

Inline "Change time" panel fetches `/api/order/day/<date>/` (`api_day_availability` returns `available`) but `buildSlotChipsHtml` tests `s.full`, which is always undefined, so full/closed slots render as selectable.

**Repro:** Customer opens Change time, picks a slot that is full → checkout submits it → 422 `slot_full` with the broken recovery from Finding 4.

**Fix:** Use `!s.available` (or return `full` from the API as basket's `/api/availability` does).

### 6. Stale stored day traps the customer with no visible cause
**File:** `src/static/js/basket.js:70`

A stored `dayIso` that is no longer in the orderable list (day passed cutoff overnight) is kept as `state.dayIso` and not re-seeded (`dayIso: storedDayIso || days[0].iso` + `if (!storedDayIso && ...)`), while chip 0 renders as selected. `checkout.js`'s `currentDay()` then returns null and blocks submit.

**Repro:** Customer builds a basket for "today" at 09:00 with a 10:00 cutoff, returns at 10:30: basket shows the first chip highlighted and Continue enabled, checkout shows "Collect —" and "Please go back to your basket and choose a collection day." Going back shows a chip already selected, so the loop never resolves unless they click a different day.

**Fix:** If `storedDayIso` isn't in `days`, reset to `days[0].iso` and call `setDayIso()`.

### 7. Slot state wiped or stale on basket revisit
**File:** `src/static/js/basket.js:234`

`loadDay()` unconditionally nulls `state.slot`/`slotId` and the `BKCart` slot on entry, and the initial render calls `loadDay` whenever the stored day isn't index 0 — so merely revisiting `/basket/` wipes a saved non-first-day slot. Conversely (line 106), a stored slot whose chip is now full loses its highlight but stays in state, so Continue remains enabled.

**Repro:** Pick Wed + 12:00, Continue, then on checkout click "back to choose a different time" or browser Back → basket has forgotten 12:00; checkout guard bounces them again. Or: stored slot fills overnight → no chip highlighted, but the hint still says "Slot 12:00" and Continue works → guaranteed `slot_full`.

**Fix:** Only clear the slot when the day actually changes; after rendering, drop the slot if its chip is missing or full.

### 8. Global throttle key locks out all mobile-only lookups site-wide
**File:** `src/core/lookup.py:101`

Mobile-only lookups call `record_lookup_attempt(ip, '')`, so the throttle key is the literal empty string, shared by every mobile-only lookup from every IP. `check_lookup_throttle` trips on that global key after 10 uses per hour.

**Repro:** Eleven different customers use mobile-only lookup within an hour (or one attacker sends 10 requests) → every subsequent mobile-only lookup site-wide returns the generic "couldn't find" error for up to an hour.

**Fix:** Skip the order-scope record/check when order number is blank (keep the IP scope).

## Medium

### 9. Option value validation gaps allow price manipulation
**File:** `src/public/api.py:165`

`option_value_ids` is only checked to be a list of ints: duplicates and values belonging to other dishes are accepted, and `reserve()` prices `[option_values[vid] for vid in line.option_value_ids if vid in option_values]` per occurrence with no dish ownership check. `isinstance(x, int)` also admits `True`/`False` for `slot_id`, `dish_id`, `quantity`.

**Repro:** POST `/api/checkout` with `option_value_ids: [42, 42, 42]` where 42 is a −R5 discount value → line priced with the delta applied 3 times; or attach another dish's negative-delta option to any dish. `quantity: true` passes as 1, `slot_id: true` as slot 1.

**Fix:** Dedupe, reject booleans (`type(x) is int`), and validate values belong to the line's dish (or let `reserve()` raise).

### 10. No brute-force protection on customer login; enumeration in signup messages
**File:** `src/public/views.py:750` (login), `:783`/`:791` (signup)

`customer_login` has no throttle or lockout (`core.auth`'s D-12 lockout is staff-only) and no CSRF/rate protection beyond Django's form CSRF. Combined with the enumeration-friendly signup messages ("An account already exists…" vs "may already be linked…"), passwords can be brute-forced against a known mobile number.

**Repro:** Script POSTs `/account/login/` with `mobile=0821234567` and a password list at full speed; nothing counts failures.

**Fix:** Reuse `core.auth.register_failed_login`/`is_locked_out` semantics for Customer, or throttle via `ThrottleEvent` like lookup.

### 11. Past guests can never sign up; guest checkout can overwrite a registered name
**File:** `src/public/views.py:784` (plus `capacity.py:314`)

Signup rejects any pre-existing Customer row without a password, but `reserve()` → `_upsert_customer` creates a Customer row on every checkout — so anyone who has ever placed a guest order can never sign up. A guest checkout under a registered customer's number also rewrites that customer's `full_name`.

**Repro:** Guest orders, later clicks "Create account" with the same mobile → "An account may already be linked to this number — contact us to verify ownership." — permanently, with no path to resolve.

**Fix:** Allow password creation on guest rows via an OTP/lookup-style proof (order number + mobile), or at least tell the customer what to do next.

### 12. Idempotency key never rotates on field edits
**File:** `src/static/js/checkout.js:48`

The Idempotency-Key is generated once per page load and only rotated on slot change/line removal. Editing name, mobile, note, payment method, or the policy checkbox after any request changes the body hash, so the server returns 409 `idempotency_conflict` with no recovery. A concurrent double-submit races the filter/create in `api.py:190-257` into an `IntegrityError` 500.

**Repro:** Place order → 400 "Full name must be 2-80 characters" → fix the name → Place order → 409 "This Idempotency-Key was already used with a different request." forever; only a reload clears it.

**Fix:** Regenerate the key whenever the payload changes (or on every non-2xx), and catch `IntegrityError` on the key insert.

### 13. Unmapped field errors and unbounded quantity stepper
**File:** `src/static/js/checkout.js:103`, `src/static/js/basket.js:325`

`fieldErrorEls` only maps `name`/`mobile`/`accept_policies`, so 400s on `lines`/`date`/`slot_id`/`payment_method` render only "Some fields need attention." Basket's increment stepper has no upper bound, while the API caps quantity at 20.

**Repro:** Customer taps + to 21 for a party order → Place order → "Some fields need attention." with no field highlighted and no hint that 20 is the max.

**Fix:** Clamp the stepper at 20 and surface unmapped field errors in the general error text.

### 14. Status-page auto-refresh discards a selected proof file
**File:** `src/templates/public/order_status.html:22` (plus `eft.js:94`)

The 30s `<meta http-equiv="refresh">` fires on `awaiting_eft`/`payment_review` — the very page with the proof-upload `<input type=file>`. `eft.js` gives no `Content-Type` guard, so HTML error responses read as "check your connection."

**Repro:** Customer picks a photo, is still reading the bank details 30s later → page reloads and the selection is gone (repeatedly, on slow uploads). Separately, a CSRF-rotated 403 HTML page shows "Couldn't reach the server" and they retry the same file.

**Fix:** Replace meta refresh with `eft.js` polling that pauses while a file is selected/uploading; add the same non-JSON guard `checkout.js` has.

### 15. Repeat-order button dead-ends; blank EFT hold-time copy
**File:** `src/static/js/checkout.js:461`, `src/templates/public/order_status.html:187`

`rc_last_order_v1` is written at order creation and home.html's Repeat module links it to `/reorder/`, which the view rejects unless status is COLLECTED, and never clears it on cancel/expiry. The EFT status page also renders `{{ eft_hold_minutes }}`, which `order_status()` never passes, printing "held for  minutes."

**Repro:** Guest places an EFT order, goes Home → "Order CT-… again" → bounces to "Only a collected order can be reordered." If the order expires, the button dead-ends forever. On the same status page, the hold copy reads "Your slot is held for  minutes."

**Fix:** Only offer Repeat for collected orders (or link to the status page), and pass `settings.eft_hold_minutes` (or use `{{ settings.eft_hold_minutes }}` directly).

## Lower severity — verified, not fully written up (cut by report length, not by confidence)

- `order_auth_<token>` cookies (`views.py:687`/`715`) are set and never read anywhere — dead code that implies an auth check that doesn't exist.
- `status_ui.py:44` maps `cash_request` to the "Confirmed" step while the copy says the kitchen hasn't confirmed.
- `lookup.html:83` compares against non-existent statuses `accepted`/`collected_cash`, so most orders get no badge.
- `dish.js:105` dereferences `#dd-add`, which the sold-out branch doesn't render (TypeError).
- `item-sheet.js:110` and the server only enforce the Spice group, so `required` non-spice options are never enforced.
- `order.js:270` calls `BKItemSheet.updateCatalog`, which doesn't exist, so the item sheet keeps day-1 sold-out data after a day switch.
- `cart.js:189` `upsertLine` merges same dish+options lines and silently overwrites the earlier kitchen note.

## Suggested order of work

1. Findings 1–2 first — they expose other customers' data.
2. Findings 3–8 next — each breaks a live customer journey outright.
3. Findings 9–15 as follow-up hardening/UX passes.

Recommend one commit per finding so each is easy to review and deploy independently, following the project's rebuild-on-deploy rule (`docker compose up -d --build web`).
