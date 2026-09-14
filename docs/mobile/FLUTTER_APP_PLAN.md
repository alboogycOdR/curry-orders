# Flutter Android app (poster variant) — live status

Source of truth for **what is done** on the native Android app. Design
source of truth for visuals: [`../../updates0909/handover_poster_variant/Roti Connect Poster Variant - Design & Style Guide.md`](../../updates0909/handover_poster_variant/Roti%20Connect%20Poster%20Variant%20-%20Design%20%26%20Style%20Guide.md)
and its [README](../../updates0909/handover_poster_variant/README.md) (open
questions/what's-not-yet-designed sections still apply here). Backend
feasibility notes (superseded by the decisions below): [`FLUTTER_FEASIBILITY.md`](FLUTTER_FEASIBILITY.md).

**Decisions locked in (2026-09-14):**
- Android only, not iOS. No App Store/HTTPS blocker.
- Native Flutter UI (not a WebView wrapper) — screens rebuilt in Dart from
  the poster design tokens, backed by a small JSON API.
- Distribution for now: sideload APK (`flutter build apk`). No Play Store
  work yet.
- API stays inside this repo, plain Django views + `JsonResponse` in
  `src/public/api.py` (same pattern as the existing checkout/proof/
  availability endpoints) — no new DRF dependency.
- App lives in `mobile/` in this repo (monorepo, not a separate repo).

Status values: `todo` · `in_progress` · `done` · `blocked`

---

## Phase 0 — Toolchain

- **Status:** done
- Flutter 3.41.6 (stable), Android SDK 37.0.0, licenses accepted, `flutter doctor` clean, verified on this machine 2026-09-14.

---

## Phase 1 — Backend: JSON API for the app

Extends `src/public/api.py`. Reuses `core`/`public.views` helpers exactly
like `views_v2.py` does for the poster web variant — no duplicated
business logic.

- **Status:** in_progress
- **Depends on:** none

Mounted at `/api/v1/` only on the poster-variant deploy
(`config/urls_v2_root.py` → `public/urls_v1_api.py`), matching
`mobile/lib/data/api_client.dart`'s base URL. Auth decision: **Django
session cookie**, same mechanism as the web (`public.customer_sessions`)
— no separate token scheme. The app calls `GET csrf/` once to receive
`csrftoken`, then echoes it back as `X-CSRFToken` on every POST (`dio`
+ a cookie jar on the Flutter side, not yet wired — Phase 2 follow-up).

### Work items

- [x] `GET /api/v1/csrf/` — `ensure_csrf_cookie`, sets the cookie the app echoes back on POSTs
- [x] `GET /api/v1/days/` — new `orderable_days_json()`, added during Phase 2/3 work once it became clear the app has no other way to know which dates are actually orderable (open + before cutoff) — `availability()` only rejects a date outside the raw preorder-days horizon, a different check
- [x] `GET /api/v1/availability/?date=` — re-exposes the existing `availability()` view verbatim (dishes + categories + slots for a date; covers the menu-with-slots need, no separate `/menu/` endpoint added)
- [x] `POST /api/v1/checkout/` — re-exposes the existing `checkout()` view verbatim
- [x] `POST /api/v1/orders/<token>/proof/` — re-exposes the existing `upload_proof()` view verbatim
- [x] `GET /api/v1/orders/<token>/` — new `order_status_json()`; refactored `public.views.order_status`'s context-building into `_order_status_context()`/`_order_status_lookup()` so both the HTML and JSON views share one query/status/EFT-panel/stepper implementation
- [x] `POST /api/v1/lookup/` — new `lookup_json()`, same throttle/generic-error discipline as `public.views.lookup`
- [x] `POST /api/v1/auth/login/` — new `login_json()`, password only (**v1 Account decision — no OTP/magic-link/Send-code**), shares the `login_ip` throttle bucket with the web login
- [x] `POST /api/v1/auth/signup/` — new `signup_json()`, mirrors `public.views.customer_signup` field-for-field including the account-takeover guard
- [x] `POST /api/v1/auth/logout/` — new `logout_json()`
- [x] `GET /api/v1/account/` — new `account_json()`, 401 `auth_required` when signed out
- [x] `GET /api/v1/account/orders/` — new `account_orders_json()`, order history for reorder support
- [x] Auth mechanism decided: Django session cookie (see above)
- [x] Tests: `tests/integration/test_mobile_api.py` — 15 tests (csrf, days, order status, lookup incl. auth-required/throttle, signup/login/logout/account, account orders). `pytest --collect-only` clean across all 487 repo tests. **Still not run against a live DB** — no local Postgres reachable on this machine. Run `py -3 -m pytest tests/integration/test_mobile_api.py tests/integration/test_availability_api.py tests/integration/test_customer_auth.py tests/integration/test_screens.py -q` against a real DB before trusting this Phase done.

---

## Phase 2 — Flutter app scaffold

- **Status:** done
- **Depends on:** none (can start in parallel with Phase 1 using mock data)

### Work items

- [x] `flutter create` project at `mobile/` (verified: `flutter doctor` clean, `flutter analyze` clean, `flutter build apk --debug` succeeds — 2026-09-14)
- [x] Design tokens ported to Dart (`lib/theme/poster_tokens.dart` — colour, shadow, spacing/radii, type scale, motion easing/durations from guide §4/§5.2/§6) + `lib/theme/poster_theme.dart` (`ThemeData`)
- [x] Barlow Condensed font bundled — converted from the web build's own `src/static/fonts/*.woff2` via `fonttools` (Flutter needs `.ttf`, not `.woff2`) into `mobile/assets/fonts/`, registered in `pubspec.yaml`. Re-run the conversion (documented inline in `pubspec.yaml`) if the web fonts are ever updated — there's no automated sync between the two.
- [x] App shell: 4-tab bottom nav — Home, Menu, Basket, **Account** (not "Orders" — see the IA decision under Phase 3) — `lib/app/shell.dart` (`AppShell`) + `lib/app/router.dart` (`go_router` `StatefulShellRoute.indexedStack`, one stack per tab, plus `/checkout` and `/orders/:token` as full-screen pushes outside the shell). Basket badge is still wired to a static `0` in `AppShell`'s constructor param, not live-connected to `basketProvider` — small follow-up.
- [x] `dio` API client pointed at `http://204.168.249.99:8105/api/v1/` — `lib/data/api_client.dart`, now with an in-memory `CookieJar` (`dio_cookie_manager`) carrying the Django session, and an interceptor that reads `csrftoken` from the jar and attaches `X-CSRFToken` on every mutating request. `main.dart` calls `primeCsrf()` once at startup. **Cookie jar is in-memory only** — app restart means signing in again; persisting it (`PersistCookieJar` + `path_provider`) is a reasonable Phase 4 addition.
- [x] Android manifest: `INTERNET` permission (main manifest, not just the debug-only one Flutter generates by default) + `network_security_config.xml` allowing cleartext HTTP to `204.168.249.99` only (the dev deploy has no TLS yet — docs/DOMAIN_AND_SSL.md). Delete both the config file and this carve-out once a real HTTPS domain exists.
- [x] State management: Riverpod (`flutter_riverpod`) — `lib/state/`: `api_providers.dart` (client/repository/availability/orderable-days/order-detail), `auth.dart` (`AuthNotifier`, restores session on app start), `basket.dart` (`BasketNotifier`, in-memory cart), `selection.dart` (selected day/category UI state)
- [x] Data layer: `lib/data/models.dart` (hand-written, not code-generated — the payloads are small/stable enough that `json_serializable`/`freezed` isn't worth the build_runner step yet), `api_exception.dart`, `repository.dart` (one method per endpoint, maps every non-2xx response to `ApiException` in one place)
- [x] Real screens replace every placeholder — see Phase 3

---

## Phase 3 — Screens

- **Status:** in_progress — every screen exists and runs against real API data; dish options and reorder are the two known real gaps left (see work items)
- **Depends on:** Phase 1 (real data), Phase 2 (shell)

**Explicit direction (2026-09-14): the app's information architecture is
not a 1:1 port of the website's.** The poster variant's own IA is a
*web* answer — a single scrolling promotional page plus drawer/modal
overlays, designed to be found cold by a browser visitor with no
account. A native app is opened by someone who already has it installed,
usually already signed in, wanting to reorder or check a live order fast
— optimise for that, not for replicating scroll sections. Concretely,
reconsider (don't default-inherit) at least these before building
screens, and record the actual decision here once made:

- **Account deserves a real home**, not "no tab of its own" (poster
  README open question 6). Push notifications (Phase 4) *require* an
  identified user; a native app's whole value proposition here is the
  repeat customer, not the cold visitor. A 5th tab or a merged
  Orders+Account tab are both more native-appropriate than the web's
  omission.
- **Home should not be a scroll-replica** of hero → collection → menu
  teaser → promise panel → steps → final CTA. A returning app user
  doesn't need "how ordering works" or the owner-promise panel on every
  open — that's first-visit/marketing content, better suited to a
  one-time onboarding flow or an About/Help screen than permanent Home
  real estate. Home should answer "what can I order right now, and
  what's the status of my last order" fast.
- **Basket-as-drawer has no native equivalent** (already flagged). Don't
  just pick "basket screen instead of drawer" and call the IA question
  closed — consider whether a persistent bottom sheet / mini-basket bar
  (visible while browsing Menu, native pattern in most food-ordering
  apps) serves better than a full tab switch for every add.
- **Order lookup by number+mobile is a *guest* affordance** — the poster
  web variant needs it because most visitors aren't signed in. In an
  installed app, a signed-in user should default straight to their own
  Orders/history; keep lookup available (e.g. for tracking an order
  placed as a guest on the web) but don't give it equal weight to a
  native user's own order list.
- **Checkout as one long scrolling form** is a web pattern. Consider a
  native multi-step flow (review → payment method → confirm) or at
  minimum native input affordances (date/slot pickers, not custom chip
  grids) where they serve the same data better on a phone.
- Category filters/slot grids/etc. — evaluate native widgets (e.g.
  platform date pickers, sheets) against the poster's exact visual chip
  pattern case by case; visual *tokens* (colour/type/spacing) still come
  from `poster_tokens.dart`, but *interaction shape* doesn't have to
  copy the web DOM structure.

**Decisions actually made (2026-09-14), building on the principles above:**

- **Account is a real 4th tab**, replacing "Orders" — `app/shell.dart`
  now has Home / Menu / Basket / **Account**. `features/account/
  account_screen.dart` merges what the web build keeps separate: signed-in
  profile + order history, signed-out login/signup, *and* guest order
  lookup (a `SegmentedButton` switches between Sign in / Sign up / Find
  order). One screen, three modes, rather than three separate surfaces.
- **Home is not a scroll-replica.** `features/home/home_screen.dart`
  leads with a collection-status card ("Ordering for Fri 19 Sep" + a
  "See the menu" CTA) and, for a signed-in customer with order history,
  a "your last order" card straight into `OrderDetailScreen`. No promise
  panel, no numbered steps, no final CTA — that marketing content isn't
  built anywhere yet (deliberately; see the principle above).
- **Basket is its own tab** (a native screen, not a web drawer) — but
  Menu carries a persistent bottom bar ("3 items · R255 →") whenever the
  basket is non-empty, so adding items doesn't force a tab switch each
  time. That's the "mini-basket bar" compromise the principle above
  named as worth considering.
- **Checkout is section-grouped**, not the plain long scroll — Order
  summary / Payment / Your details as distinct blocks on one screen. Not
  a full multi-step wizard yet (flagged as a further-native option, not
  built) — this is a smaller, real step short of that.
- **Lookup is folded into Account**, not given equal top-level billing —
  it's the third `SegmentedButton` mode, reachable but not a tab of its
  own; a signed-in customer's own history is one tap away in the same
  screen instead.

### Work items

- [x] Home (`features/home/home_screen.dart`) — collection-status card off `orderableDaysProvider`, last-order card for a signed-in customer. Real API data, not the design reference's static content.
- [x] Menu (`features/menu/menu_screen.dart`) — day chips + category filter chips + dish cards (photo/placeholder, price, sold-out, add/qty stepper) off `availabilityProvider`, persistent basket bar when non-empty
- [x] Basket (`features/basket/basket_screen.dart`) — its own screen (decision above), line list with qty steppers, day/slot picker (`_CollectionPicker`, full slots disabled), footer pinning total + Checkout (disabled until a slot is chosen)
- [x] Collection/slot picker — built as part of Basket above (`_CollectionPicker`), not a separate screen
- [x] Checkout (`features/checkout/checkout_screen.dart`) — section-grouped (see decision above): order summary, EFT/cash radio (via `RadioGroup`, not the deprecated per-tile API), name/mobile/note fields, policy checkbox, disabled-until-valid submit, real `POST /api/v1/checkout/` call with a generated `Idempotency-Key`
- [x] Order status (`features/orders/order_detail_screen.dart`) — status copy, five-dot stepper, order lines, collection address block, EFT bank-details panel. **Proof upload is not built** — the panel shows "proof already uploaded" when true but has no camera/gallery picker yet; that's explicitly Phase 4 (`image_picker` is already a pubspec dependency, unused so far)
- [x] Order lookup — folded into Account (decision above), not a separate screen/modal
- [x] Account (`features/account/account_screen.dart`) — password login/signup only, **no Send code/OTP UI anywhere** (root `CLAUDE.md`'s v1 Account decision); signed-in view shows profile + order history
- [x] Order history — `features/account/account_screen.dart`'s signed-in view, via `accountOrdersProvider`. **Reorder is not built** — tapping an order goes to its status page, there's no "order this again" action yet (the web has one at `POST orders/<token>/reorder/`; no app-side endpoint or screen exists for it)
- [ ] Dish option configurator (Spice/Extras — `DishOption`/`DishOptionValue`) — **not built**. `Dish.fromJson`/`addDish` only support a plain dish with no chosen options; a dish that has required options can currently only be added at its base price with no option selection UI. This is a real gap, not a deferred polish item — needed before checkout is trustworthy for any dish with options.
- [x] Basket badge on the bottom nav — `AppShell` now watches `basketProvider` directly (`ref.watch(basketProvider).itemCount`) instead of taking a static constructor param

---

## Phase 4 — Native platform features

- **Status:** todo
- **Depends on:** Phase 3 core screens working

### Work items

- [ ] App icon + splash screen (Roti Connect branding)
- [ ] Native camera/gallery picker for EFT proof upload (`image_picker`)
- [ ] Local basket persistence (`shared_preferences` or `hive`)
- [ ] Push notifications (FCM) — order-ready/status-change; requires Firebase project setup + `core` sending via Firebase Admin SDK on order transitions (backend work, not yet scoped)

---

## Phase 5 — Build & distribute

- **Status:** todo
- **Depends on:** Phase 3 (usable app)

### Work items

- [ ] `flutter build apk --release`, signed with a debug/release keystore (decide: throwaway debug key is fine for sideload-only distribution)
- [ ] Verify install + smoke test on a real Android device (not just emulator)
- [ ] Document install steps for the owner/testers in this file or a new `docs/mobile/INSTALL.md`

---

## Open questions (carried from poster variant README — still apply here)

1. Phone number discrepancy (082 602 3931 vs 3031) — confirm before shipping any screen with a `tel:`/dial-intent link.
2. Uber Courier — real fulfilment option or promotional text only?
3. Public-facing name: "Roti Connect" vs a promotion name.
4. Basket-as-drawer doesn't map 1:1 to native navigation — needs an explicit Flutter-idiomatic decision (Phase 3).
5. Loading/error/race states, toasts — "not yet designed" in the poster README; needs a pass for the app too.
