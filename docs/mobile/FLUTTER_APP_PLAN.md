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

- **Status:** done — deployed and verified live against the real server (see below); the pytest suite for it still hasn't run against a DB in *this* session, which is the one loose end
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
- [x] Tests: `tests/integration/test_mobile_api.py` — 15 tests (csrf, days, order status, lookup incl. auth-required/throttle, signup/login/logout/account, account orders). `pytest --collect-only` clean across all 487 repo tests. **Still not run against a live DB** in this session (no local Postgres reachable on this machine) — but the endpoints themselves are confirmed working against the real Clawsrv Postgres (see Deployed below), so the risk this was masking is lower than it was.
- [x] **Deployed** — merged to `main`, pushed, and live on Clawsrv (2026-09-14): `git pull --ff-only && docker compose up -d --build web-v2`. Verified with curl against the real server: `GET /api/v1/csrf/` → 200, `GET /api/v1/days/` → 200 with real orderable dates, `GET /api/v1/availability/?date=...` → 200 with real dish data. This is what fixed the app's initial "404 on every screen" — the backend existed only on the dev machine until this point.

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

- **Status:** done — every screen exists, runs against real API data, and the two known gaps (dish options, reorder) are closed
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
- [x] Order status (`features/orders/order_detail_screen.dart`) — status copy, five-dot stepper, order lines, collection address block, EFT bank-details panel. Proof upload (camera/gallery via `image_picker`) closed 2026-09-14 — see Phase 4
- [x] Order lookup — folded into Account (decision above), not a separate screen/modal
- [x] Account (`features/account/account_screen.dart`) — password login/signup only, **no Send code/OTP UI anywhere** (root `CLAUDE.md`'s v1 Account decision); signed-in view shows profile + order history
- [x] Order history — `features/account/account_screen.dart`'s signed-in view, via `accountOrdersProvider`. **Reorder is not built** — tapping an order goes to its status page, there's no "order this again" action yet (the web has one at `POST orders/<token>/reorder/`; no app-side endpoint or screen exists for it)
- [x] Dish option configurator — closed 2026-09-14. Backend: `GET /api/v1/availability/?date=` now calls `dishes_for_date(..., with_options=True)` and includes each dish's `options` (additive change, the web's `order.js` consumer ignores the new field). App: `features/menu/dish_option_sheet.dart` — a bottom sheet with one `RadioGroup` per required option (Spice, etc.) and a checkbox per optional one (Extras); computes the resulting unit price and a display summary, `BasketNotifier.addDish` already took `optionValueIds`/`optionsSummary`/`priceCentsOverride`, just wasn't reachable from the UI before this. Basket/Checkout line rows now show the options summary under the dish name.
- [x] Reorder — closed 2026-09-14. Backend: extracted `public.views._reorder_matched_lines` out of the existing web `reorder()` view (§11.11's re-matching rules — current prices, drop archived/deactivated dishes, best-effort option re-matching) so it's shared rather than reimplemented; new `GET /api/v1/orders/<token>/reorder/` (`reorder_json`) returns plain `{dish_id, quantity, option_value_ids, unit_price_cents, ...}` lines instead of seeding the web's `localStorage` cart. App: `OrderDetailScreen` shows an "Order these again" button when `OrderDetail.canReorder`, calling the new endpoint and feeding the result into `BasketNotifier.addLine` (a new method — merges by quantity, distinct from `addDish`'s "+1 per tap").
- [x] Basket badge on the bottom nav — `AppShell` now watches `basketProvider` directly (`ref.watch(basketProvider).itemCount`) instead of taking a static constructor param

---

## Phase 4 — Native platform features

- **Status:** in_progress — 3 of 4 items closed 2026-09-14; push notifications blocked on external Firebase project access (see below)
- **Depends on:** Phase 3 core screens working

### Work items

- [x] App icon + splash screen (Roti Connect branding) — closed 2026-09-14. No existing raster logo anywhere in the repo, so the mark was drawn from scratch: adapted the live site's own favicon (`src/templates/base_v2.html`'s inline SVG — navy circle, gold ring, gold upward arc) to a 1024x1024 master at exact `PosterColors` hexes (navy `#071124`, gold `#FFC400`, `lib/theme/poster_tokens.dart`), hand-drawn with Pillow (no cairosvg/ImageMagick on this machine — checked first) at 4x supersample + `LANCZOS` downscale for anti-aliasing, stamping overlapping filled circles along the arc's quadratic-bezier path rather than `ImageDraw.line` (the polyline stroke's mitred joints self-intersected and left moire notches at this width). Two PNGs in `mobile/assets/icon/`: `app_icon.png` (full-bleed navy + mark, legacy launcher icon) and `app_icon_foreground.png` (same mark, transparent, scaled to the adaptive-icon 66% safe zone). Wired via `flutter_launcher_icons: ^0.14.4` and `flutter_native_splash: ^2.4.7` (pinned down from `^2.4.8` — that version's `meta ^1.18.0` constraint conflicts with `flutter_test`'s SDK-pinned `meta 1.17.0`), both configured inline in `mobile/pubspec.yaml`, Android only, `adaptive_icon_background`/splash `color: "#071124"`, `android_12` block included. Ran `dart run flutter_launcher_icons` then `dart run flutter_native_splash:create` from `mobile/` — generated `android/app/src/main/res/mipmap-{hdpi,mdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher.png`, `mipmap-anydpi-v26/ic_launcher.xml` (adaptive icon XML) + `values/colors.xml`, and the splash `drawable*/{background,splash,android12splash}.png` + `launch_background.xml` + `values{,-night,-v31,-night-v31}/styles.xml`. `AndroidManifest.xml`'s `android:label="Roti Connect"` confirmed unchanged (no edit needed). `flutter analyze` → "No issues found!". `flutter build apk` intentionally not run (held until all phases done, per direction).
- [x] Native camera/gallery picker for EFT proof upload — closed 2026-09-14. `data/repository.dart`'s `RotiConnectApi.uploadProof` POSTs multipart `FormData` (one `file` field) to `orders/<token>/proof/`, parsed through the same `_parse` error path as every other method. `features/orders/order_detail_screen.dart`'s `_EftPanel` is now a `ConsumerStatefulWidget` (was stateless) with an `_uploading` flag mirroring `_OrderBodyState._reordering`'s try/catch/finally shape; when proof isn't already uploaded it shows an "UPLOAD PROOF OF PAYMENT" button that opens a bottom sheet (camera vs gallery, both via `ImagePicker().pickImage`), uploads the pick, and on success invalidates `orderDetailProvider(publicToken)` plus a confirmation SnackBar.
- [x] Local basket persistence — closed 2026-09-14. `state/basket.dart`'s `BasketNotifier` overrides its `state` setter (`super.state = value; _persist();`) so every mutation writes through to `shared_preferences` in one place rather than at each call site; restores on construction (`_restore()`, async — first frame can briefly show an empty basket before it resolves). `BasketLine`/`BasketState` gained `toJson`/`fromJson`; a corrupt/old-shape stored value is discarded rather than crashing the app on launch.
- [ ] Push notifications (FCM) — **blocked, not started.** Needs: (1) a Firebase project created under the owner's Google account (external — nothing in this repo can create it), an Android app registered in it, and `google-services.json` added to `mobile/android/app/`; (2) the Flutter side (`firebase_core`, `firebase_messaging` packages, permission handling, token registration against the backend); (3) backend work — `core` sending notifications via the Firebase Admin SDK on order status transitions, plus somewhere to store each customer's device token. None of this is scaffolded yet — adding the Flutter packages without real Firebase config would just break the build. Whoever picks this up needs Firebase project access first.

---

## Phase 5 — Build & distribute

- **Status:** in_progress
- **Depends on:** Phase 3 (usable app)

### Work items

- [x] Release signing keystore generated 2026-09-14 — `mobile/android/app/roti-connect-upload-keystore.jks` + `key.properties` (both gitignored, never committed — see `docs/mobile/INSTALL.md`'s backup warning). `android/app/build.gradle.kts` now reads `key.properties` if present and signs release builds with it, falling back to the debug key if the file is missing (so a fresh checkout without the keystore still builds).
- [x] `flutter build apk --release --split-per-abi` — verified working (arm64-v8a/armeabi-v7a/x86_64) with the real release keystore, not the debug fallback (confirmed via `apksigner verify --print-certs` — certificate DN `CN=Roti Connect, ...`). Hit a local Gradle cache corruption on this machine partway through this session (`Could not read workspace metadata from ...\.gradle\caches\8.14\...\metadata.bin`, unrelated to any code change here) — fixed by stopping the Gradle daemon (`gradlew --stop`) and deleting `~/.gradle/caches/8.14` entirely; if this recurs, that's the fix, not a code problem.
- [ ] Verify install + smoke test on a real Android device — **not done in this session**; the earlier debug-signed APK was sent and hit a 404 (fixed by the Phase 1 deploy, see above) but a full smoke test against this final release-signed build hasn't happened yet
- [x] Document install steps for the owner/testers — `docs/mobile/INSTALL.md`

---

## Phase 6 — Staff app

- **Status:** in_progress — foundation + all 7 build groups launched 2026-09-15
- **Depends on:** Phase 3 (customer app pattern this mirrors), Phase 1's auth/API conventions

**Decisions locked in (2026-09-15, explicit user direction):**
- **Redesign each staff screen for native/mobile-first**, not a literal
  port of `/manage/`'s desktop layout — same principle Phase 3 applied
  to the customer screens. The *inventory* (which 12 areas exist, their
  grouping) mirrors the web nav exactly, for staff familiarity; each
  screen's own layout/interaction pattern does not have to.
- **Built all at once**, not staged phase-by-phase with review between
  — the whole surface (backend + app) was built in one continuous pass
  across parallel subagents, one per functional group (see below).

**Auth:** independent of customer auth — its own `StaffAuthState`/
`staffAuthProvider` (`lib/state/staff_auth.dart`), own login screen
(`lib/features/staff/staff_login_screen.dart`, email+password only,
same as the web's primary login path), own backend session check
(`GET /api/v1/staff/auth/me/`). A staff session and a customer session
coexist in the same Django session cookie (existing web behaviour,
`staff.sessions` + `public.customer_sessions`) — the app's single
shared `ApiClient`/cookie jar carries both without extra plumbing.
Entry point: a low-emphasis "Kitchen staff sign in" link on the Account
screen when not staff, a real "Staff dashboard" card once signed in
(`account_screen.dart`'s `_StaffEntryPoint`) — not a 5th bottom-nav tab
(the ~everyone who isn't staff shouldn't see staff chrome by default).

**Navigation:** staff mode is its own full-screen route stack
(`/staff/...`), entirely outside the customer `StatefulShellRoute`.
Each staff screen wraps its content in `StaffScaffold`
(`lib/features/staff/staff_scaffold.dart`) — an app bar + `Drawer`
listing all 12 areas grouped exactly like the web nav — rather than a
shared `go_router` `ShellRoute`, specifically so the 7 build groups
below could each own their own screen file(s) with zero shared-file
edits to router/shell plumbing (avoids merge conflicts between agents
working in parallel).

**Backend:** `src/staff/urls_api_mobile.py` mounts `/api/v1/staff/` in
`config/urls_v2_root.py` (poster-variant deploy only, matching the
customer API). View functions are split across several
`staff/api_mobile_*.py` modules (one per build group) rather than one
large file, for the same parallel-write-safety reason. Auth
(`login_json`/`logout_json`/`me_json`) plus the shared
`staff_login_required_json` decorator (a 401 JSON body, not the HTML
boards' 302-to-login-page) live in `staff/api_mobile.py` itself, which
every other module imports from. **Action endpoints were not
duplicated** — `staff.api.transition`/`assign_order`/`lock_prep_list`/
`close_out_day`/`move_all_orders` (the existing `/manage/api/...`
JSON endpoints the web boards' own `fetch()` calls already use) are
called directly by the app, same URLs, same session+CSRF auth. Only
each screen's *read* side needed a new JSON endpoint.

### The 7 build groups (backend + mobile screen(s) together, one subagent each)

| Group | Screens | Backend module | Mobile screen file(s) |
|---|---|---|---|
| 1 | Inbox, Kitchen desk | `api_mobile_boards.py` | `features/staff/inbox/`, `features/staff/kitchen/` |
| 2 | Collection, Cash | `api_mobile_collection_cash.py` | `features/staff/collection/`, `features/staff/cash/` |
| 3 | Payments, Calendar | `api_mobile_payments.py` | `features/staff/payments/`, `features/staff/calendar/` |
| 4 | Daily controls, Help | `api_mobile_daily_controls.py` (Help needs none — see below) | `features/staff/daily_controls/`, `features/staff/help/` |
| 5 | Menu editor (solo — biggest: dish CRUD, image upload, options/values CRUD) | `api_mobile_menu.py` | `features/staff/menu/` |
| 6 | New assisted order (solo — checkout-equivalent form/capacity flow) | `api_mobile_assisted_order.py` | `features/staff/assisted_order/` |
| 7 | Settings, Team (both owner/admin-gated) | `api_mobile_admin.py` | `features/staff/settings/`, `features/staff/team/` |

**Help** deliberately has no backend endpoint and no native content port
— it opens `https://roticonnect.duckdns.org/manage/help/#<anchor>` in
the device browser (`url_launcher`, added to `pubspec.yaml`) from a
native list of section links, rather than re-porting 600+ lines of
`docs/STAFF_GUIDE.md` content that would drift out of sync with the
source guide.

**Full functional spec per screen** (data shown, every action, role
gates, validation rules) was captured live from the actual `src/staff/`
source on 2026-09-15 before this phase started — see each build group's
own module/screen docstrings for the specific rules that applied to it;
the source survey itself was not kept as a separate doc (it was a
one-time input to the build, not an ongoing reference — `src/staff/`
itself is the source of truth going forward).

### Known gaps after this phase
- No Dart-side tests for any staff screen (same pre-existing gap as the
  customer side — see Phase 5's own open item).
- Staff Google sign-in isn't wired into the app (customer Google
  sign-in isn't either — tracked as one combined follow-up, not
  staff-specific).
- Real-time/polling: none anywhere in the web staff boards today either
  (every JS file says so explicitly) — this phase doesn't add any; a
  "pull to refresh" gesture per screen is the mobile-native minimum bar
  and should exist, full push-based live updates would be new ground
  neither surface has.
- Not verified on a real device yet (same open item as Phase 5).

## Phase 7 — App became staff-only

- **Status:** done — 2026-09-15, same day as Phase 6
- **Depends on:** Phase 6 (the staff surface this repurposes the whole app around)

**Explicit direction:** the app is now a **staff companion app only** —
every customer-facing screen (Home, Menu, Basket, Checkout, Account,
Order status/lookup/reorder, customer sign-in) was removed. Not
disabled behind a flag, not hidden — deleted, along with the state/
data/util code that only ever served them (`state/auth.dart`,
`state/basket.dart`, `state/selection.dart`, `util/idempotency.dart`,
`data/repository.dart`, `app/shell.dart`, and every customer-only
model in `data/models.dart`). The customer-facing website/poster
variant is unaffected — this only touches `mobile/`; the Django
backend's `/api/v1/...` customer endpoints (`public/api.py`) were left
running (harmless if unused by the app, and the code stays available
if a customer app is ever wanted again).

**IA decisions:**
- **Bottom nav, not a drawer**: Inbox / Kitchen / Collection / **More**
  — the three highest-frequency, during-service boards get a direct
  tab (one tap, not hamburger-then-item); everything else (Calendar,
  Payments, Cash, Daily controls, Menu editor, New assisted order,
  Help, Settings, Team) lives in More's own list, replacing Phase 6's
  hamburger `Drawer` that used to wrap every single screen. Same
  bottom-tab-plus-More pattern the (now-removed) customer app already
  proved out — reused for consistency, not reinvented.
- **Auth is the app's front door.** No more "Account tab with a
  buried staff sign-in link" — there is no Account tab. `app/
  staff_shell.dart` (the `StatefulShellRoute`'s `builder`) doubles as
  the auth gate: watches `staffAuthProvider` directly, shows a splash
  while restoring, bounces to `/staff/login` the instant it's anything
  but signed-in (cold start *and* a session expiring mid-use — the
  staff session's own 12h absolute / 2h idle lifetime). No
  router-level `redirect:` wiring needed; a plain widget-level check
  in the shell's `build()` was simpler and lower-risk than reactively
  rebuilding `GoRouter` off Riverpod state.
- **Staff identity moved to the top of the More screen** (avatar,
  name, role) — replaces the old drawer header; there's nowhere else
  for it now that Account is gone.
- **One shared customer-era file survived**: `shared/dish_option_sheet.dart`
  (moved out of the deleted `features/menu/`) — New assisted order
  still needs a dish-options configurator and reuses this one rather
  than building a second copy. `data/models.dart` was pruned to just
  the three model classes that widget (and its `toSharedDish()`
  adapter in `assisted_order_screen.dart`) actually needs
  (`Dish`/`DishOption`/`DishOptionValue`) — every other model in that
  file (orderable days, availability, order status, account, reorder,
  featured dish) was customer-only and removed with it.
- `pubspec.yaml`: `shared_preferences` dropped (only ever backed the
  customer basket's local persistence). Everything else staff mode
  already depended on (`dio`/`dio_cookie_manager`, `image_picker`,
  `url_launcher`, `go_router`, `flutter_riverpod`) is unchanged.
- App identity: Android launcher label and the `MaterialApp` `title`
  both changed to "Roti Connect Staff" for clarity on a device — the
  app icon/splash art were **not** regenerated (still the plain "Roti
  Connect" mark); a distinct staff-branded icon is a reasonable
  follow-up, not done here.

**Known gap carried forward:** a staff screen reached only via the
More tab (not one of the three bottom-tab screens) has no *individual*
redirect-on-session-expiry guard of its own — if the 12h/2h session
lifetime lapses while a staff member is deep in, say, the Menu editor,
that screen's own API calls will 401 and show whatever error handling
that screen already has, rather than bouncing to `/staff/login`
immediately. Returning to a bottom-nav tab (or relaunching the app)
does trigger the shell's own check correctly. A global 401-triggers-
logout interceptor on the shared `ApiClient` would close this gap
fully; not built here.

## Phase 8 — Google Sign-In, native Help, push notifications, branding

- **Status:** in_progress — everything buildable without external config is done; push notifications need a Firebase project (being set up with the user, in progress) before they can actually fire
- **Depends on:** Phase 7 (the staff-only app this extends)

### Google Sign-In (done, needs one Google Cloud Console step)
Native sign-in (`google_sign_in` package) alongside the existing
password login on `StaffLoginScreen` — not a replacement. Backend:
`core.google_auth.verify_id_token()` (new — verifies a native ID token
via Google's `tokeninfo` endpoint, distinct from `get_verified_
google_user()`'s authorization-code flow the web uses) and `POST
/api/v1/staff/auth/google/` (`staff/api_mobile.py::google_login_json`),
both converging on the same `staff.services.try_grant_staff_session`
the web's own Google callback uses — one allowlist check, one
session-granting path, three entry points now (web password, web
Google, app password, app Google — the shared function doesn't care
which). Verified live: a real HTTP call to Google's `tokeninfo`
endpoint correctly rejects a garbage token with a clean 400, not a 500.

**Still needed, external, one-time**: an **Android** OAuth client
(distinct from the existing web client `GOOGLE_CLIENT_ID`) registered
in the same Google Cloud project, under package name
`com.rotiConnect.roti_connect` and the release keystore's SHA-1
fingerprint (`2E:49:BA:07:33:FD:41:A1:EA:F7:23:54:1E:16:B7:64:90:77:48:7E`
— extracted from `mobile/android/app/roti-connect-upload-keystore.jks`).
Without it, Google Play Services will refuse the sign-in on-device even
though every line of code on both sides is already correct and
verified. `google_sign_in`'s `serverClientId` is set to the existing
web `GOOGLE_CLIENT_ID` (`mobile/lib/state/staff_auth.dart`) so the ID
token it returns is already audienced for the server that needs to
verify it — no code change once the Android client exists, this is
purely a Console registration step.

### Native Help (done)
`docs/STAFF_GUIDE.md`'s full content (16 sections) ported to real
Flutter widgets under `mobile/lib/features/staff/help/` — no more
linking out to the web page. Structured content data
(`help_content.dart`) + reusable rendering widgets (`help_widgets.dart`
— colour-coded callouts, a stacked-card table renderer, a numbered
step/timeline view for the two order-flow sections, role badges, an
FAQ accordion) + an icon-badged index screen + a per-section detail
screen. Built by a delegated subagent, then spot-checked against the
source guide for completeness.

### Push notifications (in progress — code done, delivery pending Firebase)
Backend, all deployed and independently verified against a real DB:
- `core.models.DeviceToken` (migration `0007_device_token`) — one FCM
  token per staff device, many-to-one on `User`.
- `core.notifications.send_to_user`/`notify_staff` — fail-soft by
  design: a no-op (logged, not raised) whenever
  `settings.FIREBASE_CREDENTIALS_PATH` is unset, and any Firebase API
  error is caught and logged rather than propagated, so a
  notifications outage can never break an order transition or
  checkout. Auto-prunes a `DeviceToken` row once Firebase reports its
  token as unregistered/not-found.
- Three trigger points, matching what was asked for explicitly — "new
  order arrives", "meals get done", "a pickup is placed": `public/
  api.py::checkout` (also covers real website orders — this view is
  shared with the unversioned `/api/checkout` the site itself calls),
  `staff/api_mobile_assisted_order.py::assisted_order_json` and
  `staff/views.py::assisted_order_new` (both order-creation paths, app
  and web), and `staff/api.py::transition` for `mark_ready`/
  `mark_collected` (the one generic endpoint every board's row action
  already goes through, web and app alike — no separate app-side hook
  needed for those two). Each call is placed *after* its own
  transaction commits, never inside one.
- `POST /api/v1/staff/notifications/register/`+`.../unregister/`
  (`staff/api_mobile.py`) — the app's own token registration.
- Verified live (Django test client against a real migrated DB, no
  Firebase configured): checkout still returns 201 and creates a real
  order with `notify_staff` wired in; `mark_ready`/`mark_collected`
  still transition correctly; device-token register/re-register/
  unregister all behave correctly; nothing anywhere raised despite
  zero Firebase configuration — confirming the fail-soft design
  actually holds, not just reads that way.

Mobile: `state/notifications.dart` (a local, per-device on/off
preference — `shared_preferences`, deliberately **not** a field on the
shared business `core.models.Settings` the owner/admin-only Settings
screen edits, since gating a personal notification preference behind
admin access would stop the kitchen staff who need the alert most from
ever turning it on) and `features/staff/notifications/
notifications_screen.dart`, reached from the More tab (not nested
inside Settings, for the same reason).

**Still needed, external**: a Firebase project + `google-services.json`
(app config) + a service-account private key (server config, for
`FIREBASE_CREDENTIALS_PATH`) — in progress with the user. `firebase_core`/
`firebase_messaging` are already dependencies and the app was verified
to still build cleanly with them present but **unconfigured**
(`Firebase.initializeApp()` is deliberately not called anywhere yet —
doing so without a real `google-services.json` in place would break
the Android build outright, not just leave push non-functional).
Once both files land: add `google-services.json` to `mobile/android/
app/`, apply the `google-services` Gradle plugin, call `Firebase.
initializeApp()` + register for a token + wire it through to `POST
.../notifications/register/` in `state/notifications.dart`, and set
`FIREBASE_CREDENTIALS_PATH` in the server's `.env` pointing at the
service-account key (kept outside the repo, like every other secret
here).

### Branding (done)
- Bottom nav expanded from 4 to 6 tabs — Inbox / Kitchen / Collection /
  **Calendar** / **Payments** / More (explicit direction: promote
  Calendar and Payments off the More list onto direct tabs). Router
  (`app/router.dart`) and shell (`app/staff_shell.dart`) both updated;
  a smaller, tighter local label style keeps all six on one line at
  phone width without the app's usual nav-label style (tuned for 4-5
  items) truncating "Collection"/"Payments".
- The owner portrait ("Brandon's face") now appears small (24px
  circle) next to the section title in every screen's app bar
  (`features/staff/staff_scaffold.dart`) — the same image the web/
  poster header uses, re-exported to `mobile/assets/img/
  owner-avatar.jpg` at 160×160 (~8KB) rather than shipping the web
  original's 213KB for what's only ever a small avatar.

## Open questions (carried from poster variant README — still apply here)

1. Phone number discrepancy (082 602 3931 vs 3031) — confirm before shipping any screen with a `tel:`/dial-intent link.
2. Uber Courier — real fulfilment option or promotional text only?
3. Public-facing name: "Roti Connect" vs a promotion name.
4. Basket-as-drawer doesn't map 1:1 to native navigation — needs an explicit Flutter-idiomatic decision (Phase 3).
5. Loading/error/race states, toasts — "not yet designed" in the poster README; needs a pass for the app too.
