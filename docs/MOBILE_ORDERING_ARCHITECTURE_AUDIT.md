# Mobile Ordering Architecture Audit

**Date:** 2026-08-30  
**Scope:** Read-only audit of the existing application before a mobile-ordering redesign. No application files were modified.

## A. Technology and architecture overview

- Django 5.0, Python 3.12, PostgreSQL 16.
- Server-rendered Django templates; no React/Vue SPA.
- Vanilla JavaScript for client interaction and local cart state.
- CSS design system plus substantial page-local inline styles.
- Domain/business logic isolated in `src/core/`.
- Customer site: `src/public/`; staff operations: `src/staff/`.
- Media/proof storage: MinIO/S3-compatible storage via `src/storage/`.
- EFT payment proof flow and capacity-aware collection ordering are implemented.

Key entry points:

- `src/config/urls.py`
- `src/public/urls.py`
- `src/templates/base.html`

## B. Existing route map

| Area | Routes |
|---|---|
| Home | `/` |
| Browse menu | `/menu/?date=` |
| Product detail/configuration | `/dishes/<slug>/?date=` |
| Interactive ordering | `/order/` |
| Checkout | `/checkout/` |
| Order status / EFT proof | `/orders/<token>/` |
| Previous-order lookup | `/lookup/` |
| Reorder | `/orders/<token>/reorder/` |
| Help / policies | `/help/`, `/policies/` |
| Checkout API | `POST /api/checkout` |
| EFT proof API | `POST /api/orders/<token>/proof` |
| Staff app | `/manage/*` |

## C. Existing screen inventory

### Customer

- Home — `src/templates/public/home.html`
- Menu browse — `src/templates/public/menu.html`
- Dish detail/configuration — `src/templates/public/dish_detail.html`
- Combined order-builder/menu/cart/slot page — `src/templates/public/order.html`
- Checkout and transient confirmation — `src/templates/public/checkout.html`
- Order status, EFT instructions and proof upload — `src/templates/public/order_status.html`
- Lookup, reorder, help, and policies.

### Staff

A separate authenticated management suite supports inbox, payments, kitchen, collection, calendar, menu editing, assisted orders, daily controls, and settings.

## D. Relevant component inventory

This codebase uses template/JavaScript composition rather than a component framework.

- Shared shell/header/footer: `src/templates/base.html`
- Cart state and header badge: `src/static/js/cart.js`
- Inline ordering interactions: `src/static/js/order.js`
- Product configuration: `src/static/js/dish.js`
- Checkout submission: `src/static/js/checkout.js`
- Product/menu query layer: `src/core/menu.py`
- Capacity-safe reservation layer: `src/core/capacity.py`

## E. Existing menu and product data flow

`Dish` supports name, descriptions, price, category, portion, dietary/allergen fields, image media, availability, and notes. `DishOption` and `DishOptionValue` support required/optional modifier groups, price deltas, ordering, and availability.

```text
Dish / DishOption / DishOptionValue
  → core.menu queries date-specific availability
  → public views
  → menu / dish-detail / order templates
  → browser localStorage cart
  → POST /api/checkout
  → capacity reservation + immutable order-line snapshots
```

This is a suitable foundation for mobile product cards and a configuration sheet; a new product schema is not required.

## F. Existing basket/cart data flow

- Cart is browser-only `localStorage`, not a database draft.
- Lines are keyed by dish ID, or `dishId:optionId,optionId` for configured variants.
- Cart stores display name, price in cents, and quantity.
- Day, slot label, slot ID, and payment preference are separate localStorage keys.
- Checkout re-reads live database pricing and availability before creating an order.

The current basket is embedded in `/order/` and summarized at `/checkout/`; there is no dedicated basket screen.

## G. Existing authentication flow

- Customers are guest users by deliberate product decision.
- Customer records are created/updated from checkout name and mobile number.
- There are no customer login, sign-up, profile, addresses, loyalty, or password-reset flows.
- Staff have separate custom email/password session auth with Argon2id, lockout, forced first-password change, and owner/manager roles.

Customer accounts were subsequently approved for Phase 1 follow-up. The first slice now uses the existing mobile-keyed Customer record with a nullable password hash and an independent customer session layer; profile, address book, order history, and password-reset delivery remain later slices.

## H. Existing checkout and order flow

```text
Menu browse or order builder
  → select date + collection slot
  → checkout: name, mobile, note, payment, policies
  → POST /api/checkout with idempotency key
  → capacity-safe reservation transaction
  → EFT hold or cash-request state
  → order-status page
  → EFT proof upload / staff operational workflow
```

Current fulfilment is **collection only**. There is no delivery address, delivery pricing, store selection, or multi-store model.

## I. CURRENT IA

```text
APPLICATION
├── Home (/)
│   ├── Hero / featured picks
│   └── How collection works
├── Menu (/menu/)
│   ├── Date selector
│   ├── Category sections
│   └── Dish cards → Dish detail
├── Dish detail (/dishes/<slug>/)
│   ├── Options / modifiers
│   └── Add to local cart
├── Order (/order/)
│   ├── Full menu
│   ├── Inline quantity changes
│   ├── Day + collection slot
│   └── Embedded order sheet
├── Checkout (/checkout/)
│   ├── Customer details
│   ├── Payment choice
│   └── Order summary
├── Order status (/orders/<token>/)
│   ├── EFT proof upload where applicable
│   └── Collection details after confirmation
├── Support
│   ├── Lookup
│   ├── Reorder
│   ├── Help
│   └── Policies
└── Staff (/manage/)
    ├── Inbox / calendar / kitchen / collection
    ├── Payments / cash requests
    ├── Daily controls / menu editor
    └── Assisted orders / settings
```

## J. Gap analysis

| Area | Current implementation | Target pattern | Gap | Recommendation | Priority |
|---|---|---|---|---|---|
| Home | Marketing/discovery page | Mobile discovery hub | No search, order context, mobile shell | Retain content; add compact discovery modules | P1 |
| Primary navigation | Sticky desktop-style header with order/checkout icons | Persistent five-tab mobile nav | No Home/Menu/Basket/Account/More shell | Introduce customer mobile shell only | P0 |
| Menu | Separate browse page and order page | One shoppable menu screen | Ordering is split and duplicated | Make `/menu/` the primary shop surface incrementally | P0 |
| Categories | Vertical sections | Horizontal category tabs + active category | No horizontal taxonomy navigation | Add category rail using existing `Dish.category` | P1 |
| Search | None | Menu/product search | No discovery search | Client-side search initially; server endpoint only if catalogue grows | P1 |
| Product cards | Text-only browse cards | Image, description, price, add | No image/card add action | Use existing `image_media`; direct/add-or-configure action | P1 |
| Product details | Full page with options | Mobile product configuration | Functional but not sheet-like/mobile optimized | Reuse data model; present as bottom sheet/drawer on mobile | P1 |
| Product configuration | Options exist | Required rules and clear review | API does not enforce option ownership/required selections | Fix server validation before exposing quick add broadly | P0 |
| Store selection | One implicit collection location | Order context/store selector | Single-store schema only | Show Collection context; do not build store selector yet | P1 |
| Delivery/collection | Collection only | Explicit fulfilment context | Delivery is unsupported | Make collection prominent; defer delivery pending business scope | P0 |
| Basket | Embedded order sheet, checkout summary | Dedicated basket screen | No edit/remove-first basket flow | Add `/basket/` backed by existing localStorage | P0 |
| Checkout | Two-page order → checkout | Short mobile flow | Good backend; layout and recovery need work | Preserve API; compact steps and add clear review/context | P1 |
| Authentication | Guest checkout; staff auth; customer signup/login now added | Customer Account tab | Password reset/profile data still absent | Extend the customer session slice with reset delivery and profile capabilities | P1 |
| Account | Account landing, lookup, signup, login, logout | Profile/addresses/orders | Addresses and order history not yet exposed | Add authenticated customer dashboard incrementally | P1 |
| Confirmation | Real status page | Confirmation + next actions | Exists, but checkout confirmation auto-redirect is abrupt | Keep status page; improve mobile handoff | P1 |
| Responsive design | Broad breakpoints, desktop layouts stack | 360–430 first-class | Inline CSS, no safe-area/bottom-nav treatment; many small controls | Establish mobile foundation before visual changes | P0 |
| Component reuse | Shared template/JS utilities | Reusable ordering primitives | Mostly page-local markup/styles | Extract templates/partials and shared mobile JS modules incrementally | P1 |
| State management | localStorage browser state + server transaction | Explicit OrderContext | State is fragmented across localStorage keys | Wrap existing keys behind an `OrderContext` JS abstraction | P1 |

## K. Recommended TARGET IA

```text
CUSTOMER APP SHELL
├── Home
│   ├── Search
│   ├── Featured dishes
│   ├── Menu discovery
│   └── Active collection context
├── Menu
│   ├── Search
│   ├── Collection context
│   ├── Horizontal categories
│   ├── Product cards
│   └── Product configuration sheet/detail
├── Basket
│   ├── Collection date + slot
│   ├── Items, options, quantities, edit/remove
│   └── Checkout CTA
├── Account
│   ├── Find my order
│   └── Customer account features later, if approved
└── More
    ├── Help
    ├── Policies
    └── Staff login (low prominence)
```

For the current product, the initial context should be:

```text
OrderContext = {
  fulfilmentType: "COLLECTION",
  collectionDate,
  collectionSlotId,
  collectionSlotLabel
}
```

Delivery or multi-store support must not be implied until their backend contracts exist.

## L. Recommended implementation phases

1. **Mobile shell and navigation** — customer-only bottom nav, safe-area spacing, active states, preserve desktop header.
2. **Menu consolidation** — make `/menu/` the primary shop surface; category rail, search, mobile product cards.
3. **Product configuration** — reusable configuration UI; fix server-side option validation first.
4. **Order context** — formalize existing date/slot localStorage state; ensure date changes refresh valid slots.
5. **Dedicated basket** — add/edit/remove, intentional empty state, context and checkout CTA.
6. **Checkout mobile UX** — compact review/details/payment flow while retaining the existing API and capacity transaction.
7. **Account / More** — Account now has customer signup/login plus lookup; move low-frequency pages into More.
8. **Polish and hardening** — accessibility, mobile viewport testing, performance/image handling, regression tests.

## M. Files/modules most likely to change

- `src/templates/base.html` — customer shell, responsive header/footer, bottom nav.
- `src/public/urls.py` and `src/public/views.py` — dedicated basket and menu flow.
- `src/templates/public/menu.html`
- `src/templates/public/order.html`
- `src/templates/public/dish_detail.html`
- `src/templates/public/checkout.html`
- `src/static/js/cart.js`
- `src/static/js/order.js`
- `src/static/js/dish.js`
- `src/static/js/checkout.js`
- `src/public/api.py` and `src/core/capacity.py` — modifier validation and checkout contract safeguards.
- `src/static/css/broadsheet.css` — shared mobile tokens/utilities after structural work.

## N. Risks and technical constraints

- **P0: date/slot desynchronization.** `/order/` initially renders slots only for the first orderable date; changing date does not fetch date-specific slots. A selected slot can belong to a different date.
- **P0: modifier validation gap.** The checkout API accepts option IDs by shape, but current reservation logic does not visibly enforce that options belong to the selected dish or that required modifier groups are selected. Correct this before relying on quick-add paths.
- The current interactive order page can add modifier-capable dishes without configuration, whereas dish detail supports modifiers. This is inconsistent and should be resolved in Phase 3.
- Collection-only and guest checkout are explicit product constraints. Delivery, multi-store selection, customer addresses, and customer accounts require approved scope beyond mobile redesign.
- Cart state is local-only; it is suitable for the current guest checkout model but will not support cross-device recovery.
- Customer CSS is largely embedded in individual templates, so mobile refactoring needs careful extraction to avoid desktop regressions.
- Product imagery is structurally supported but real menu photos are still owner-supplied content.
- Existing backend flows, payment proof handling, capacity reservation, and staff operations should remain untouched except for narrowly scoped validation fixes.

## Recommended next step

Phase 1 is complete. Before consolidating the shoppable menu in Phase 2, add coverage and fixes for the two P0 ordering issues: date/slot synchronization and server-side modifier validation.

## Implementation progress

### Phase 1 - mobile shell and home foundation

Implemented on 2026-08-30:

- Customer-only mobile bottom navigation with Home, Menu, Basket, Account, and More destinations.
- Safe-area-aware fixed navigation, active-route states, 56px minimum navigation targets, and a live basket count.
- Compact mobile header; existing desktop and staff navigation remain unchanged.
- Dedicated mobile home composition with collection context, menu discovery entry, one featured promotion, returning-customer order lookup, discovery cards, and featured dishes.
- Existing editorial desktop home retained above the mobile breakpoint.
- Account now routes to a customer account landing page with signup/login and the existing secure order lookup; sessions are independent from staff authentication.
- Basket currently routes to checkout until the dedicated basket phase is implemented.
- More currently routes to Help, with Policies grouped under the same active destination.

Validation: 437 automated tests passed; representative customer routes were checked at 360px with no horizontal overflow; the home was visually reviewed at 390px and 1365px.

## Appendix: revised mobile home direction

### Evidence reviewed

The current home-screen PDF is a four-page editorial landing page. It contains a large wordmark, location/date/collection details, a long kitchen introduction, two calls to action, three operating statistics, a hero image, three textual featured dishes, a three-step collection explainer, and a footer. It is visually considered but too content-dense for a 360-430px ordering-app home screen.

### Mobile home objective

The mobile home screen should be a compact discovery surface. Its job is to move a customer into the menu or a featured product quickly, rather than explain the entire business and collection process before they begin shopping.

### Recommended mobile home hierarchy

```text
HOME
├── Compact branded header
├── Search menu
├── Primary promo / featured dish card
│   └── Single clear CTA: Order now
├── Optional customer entry prompt
│   ├── Message: Save time on future orders
│   └── Login / Sign up action, only if customer accounts are approved
├── Two compact discovery cards
│   ├── Our menu
│   └── Popular dishes / favourites
├── Optional lightweight promotion
└── Persistent bottom navigation
```

### Content rules

- Use one short headline or no headline; do not retain the large editorial masthead on mobile.
- Keep the main promotional card to an image, short dish name/value statement, price where relevant, and one CTA.
- Use image-led discovery cards for menu categories or featured dishes instead of explanatory paragraphs.
- Move the collection process, operational statistics, legal copy, and long kitchen story to More, Help, or a secondary desktop-oriented section.
- Keep the collection-only context visible but compact, for example: `Collection · Choose date and time`.
- Retain the existing home hero image and product-image capability where assets are available; do not use Nando's artwork or branding.

### Product constraint: login prompt

The requested central Login / Sign up invitation matches the intended mobile structure. Customer signup/login is now approved and implemented as a narrow first slice; password reset delivery, customer profile, addresses, and order history still require their own data and UX decisions. The equivalent actionable home module is:

```text
Already ordered with us?
[ Find my order ]
```

The shell routes Account to the customer account landing page, where Login and Sign up are functional and order lookup remains available without authentication.

### Implementation impact

This changes the priority of Home within Phase 1. The mobile shell and bottom navigation should be implemented together with a simplified mobile home template. The existing desktop home can remain available with responsive treatment until a deliberate desktop redesign is approved.
