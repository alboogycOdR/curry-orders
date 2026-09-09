# Roti Connect Poster Variant — Design & Style Guide

**Document purpose:** Define the design system and implementation rules for the Roti Connect website variant inspired by the client’s promotional poster.

**Variant concept:** A high-contrast, poster-led food ordering experience for Roti Connect’s weekly specials.

**Primary visual reference:** The client poster featuring the illustrated owner, navy background, electric blue outlines, gold price highlights, white display lettering, brush-stroke accents, Friday 04/09 promotion, R45 Mince Curry Roti, Windsor Park collection, and contact details.

**Prototype checkpoint:** `b6bb6af4`

---

## 1. Design Intent

This variant should feel like the client’s promotional poster transformed into a usable ordering website. It must retain the poster’s confidence, contrast, local personality, and promotional energy while adding the clarity expected from a mobile ordering flow.

The website is not intended to look like a generic restaurant website. It should feel like a bold weekly food drop with a recognizable owner-led identity.

> **Core idea:** A poster that customers can order from.

> **Design principle:** Use poster energy for attention, then use structured UI for conversion.

### 1.1 Primary user outcome

A customer should be able to understand the following within the first viewport:

- What is being sold.
- The featured price.
- The next collection date.
- When food becomes available.
- Where collection takes place.
- How to start an order.

### 1.2 Business details represented by this variant

The prototype is based on the following promotion details:

| Detail | Current variant value |
|---|---|
| Featured dish | Mince Curry Roti |
| Featured price | R45 |
| Promotion date | Friday 04/09 |
| Order deadline | 03/09 |
| Availability | From 11am |
| Collection location | Windsor Park, Kraaifontein |
| Collection method | Direct collection, with Uber Courier as an optional route |
| Contact number | 082 602 3031 |

These values must become dynamic content in production. Do not permanently hard-code a single promotion into the application.

---

## 2. Brand Personality

The variant should express the following personality traits:

| Trait | How it appears in the interface |
|---|---|
| Bold | Large condensed headlines, strong contrast, visible price treatment. |
| Local | Kraaifontein and Windsor Park references, direct collection language, owner-led identity. |
| Generous | Large food photography, strong portions, expressive descriptions. |
| Energetic | Electric blue lines, brush textures, offset shadows, promotional labels. |
| Trustworthy | Clear dates, order deadlines, pickup slots, phone number, and collection steps. |
| Personal | Illustrated owner portrait and first-person-feeling copy. |

The tone should be confident and warm without sounding corporate. It should feel like a business owner speaking directly to hungry regulars.

### 2.1 Avoid

Do not introduce:

- Cool SaaS-style gradients.
- Muted beige editorial styling from the previous design direction.
- Generic delivery marketplace UI.
- Excessive luxury restaurant language.
- Dense flyer text inside the website interface.
- Decorative Indian motifs that compete with the client’s illustrated identity.
- Cartoon imagery unrelated to the supplied owner illustration.
- Fake order confirmations or fake payment states.

---

## 3. Visual Language

### 3.1 Poster-to-website translation

The poster has a dense, promotional composition. The website should translate its visual ingredients rather than copy its exact layout.

| Poster ingredient | Website translation |
|---|---|
| Navy background | Hero, header, footer, final CTA, order drawer emphasis. |
| Electric blue rings | Avatar frames, section rules, borders, decorative outlines. |
| Gold/yellow accents | Price, featured CTA, selected states, badges, order deadline. |
| White headline text | Hero display type and dark-surface headings. |
| Brush-stroke texture | Hero background accents and separator shapes. |
| Illustrated owner | Logo/avatar, hero illustration, trust section, footer mark. |
| Food close-up | Hero food plate and menu card imagery. |
| Flyer information blocks | Collection card, pickup selector, operational notice. |
| Contact number | Header strip and footer contact action. |

### 3.2 Composition rules

Use visual tension between two sides of the layout:

- Text and offer information should occupy one side.
- The owner illustration and food should occupy the other side.
- Do not center every element in the hero.
- Let the food and character overlap slightly to create a promotional poster effect.
- Keep primary text in a controlled measure so it remains readable on mobile.
- Use hard-edged offsets and borders in place of soft gradients.

### 3.3 Texture rules

Texture should be subtle enough that it does not damage legibility.

Approved textures:

- Diagonal electric-blue brush lines.
- Irregular blue shapes behind hero content.
- Offset solid-color shadows.
- Circular outline rings behind the owner illustration.
- Thin poster-style divider lines.

Avoid:

- Animated noise that distracts from the CTA.
- Overly grainy backgrounds behind body copy.
- Multiple competing patterns in the same viewport.

---

## 4. Color System

Use design tokens. Do not scatter raw color values through the codebase.

### 4.1 Core palette

| Token | Hex | Usage |
|---|---:|---|
| `--poster-navy` | `#071124` | Primary dark background and text on light surfaces. |
| `--poster-black` | `#050A15` | Header strip, footer, deepest background. |
| `--poster-blue` | `#168CFF` | Electric blue accent, borders, active states, icons. |
| `--poster-blue-deep` | `#0C3679` | Illustration circles, secondary blue panels. |
| `--poster-blue-panel` | `#102A58` | Collection card, promise section, secondary dark surface. |
| `--poster-gold` | `#FFC400` | Prices, primary CTA, featured badges, highlights. |
| `--poster-gold-soft` | `#FFD95A` | Optional hover or pale highlight state. |
| `--poster-white` | `#FFFFFF` | Card backgrounds, hero text, high-contrast UI. |
| `--poster-paper` | `#F7F8FA` | Light content sections and forms. |
| `--poster-border` | `#D3DDEA` | Light-surface borders and dividers. |
| `--poster-muted` | `#56647A` | Secondary copy on light backgrounds. |
| `--poster-muted-dark` | `#AEB8C9` | Secondary copy on dark backgrounds. |
| `--poster-error` | `#D9343E` | Error states and validation. |
| `--poster-success` | `#55A868` | Confirmed state, only when operationally valid. |

### 4.2 Color hierarchy

Use the palette in the following order of importance:

1. Navy establishes the brand environment.
2. White provides readability and clean content surfaces.
3. Electric blue identifies brand interaction and structure.
4. Gold identifies value, urgency, and action.
5. Muted blue-gray supports secondary information.

Gold should be used sparingly enough that prices and primary actions remain special.

### 4.3 Contrast rules

- White text on navy is the primary dark-surface combination.
- Navy text on white or paper is the primary light-surface combination.
- Navy text on gold is preferred for buttons and price stickers.
- Do not use blue-gray text on navy for required information unless contrast is verified.
- Do not use gold text on white for long copy.
- Do not use blue text on blue panels without a white or border separation.

---

## 5. Typography System

The typography should resemble a bold promotional poster while remaining readable as a website.

### 5.1 Font roles

- **Display and interface font:** Barlow Condensed, using heavy weights for promotional headlines.
- **Script accent:** A brush or script fallback such as `Brush Script MT` or `Segoe Script` for short words such as `roti`, `flavour`, or `taste`.
- **Fallback display:** `Arial Narrow`, `Arial`, sans-serif.
- **Fallback script:** `cursive`.

A production implementation should use a licensed or reliable web font for the script accent if the brand requires consistent rendering. The script font must never be used for essential operational information.

### 5.2 Type scale

| Role | Desktop | Mobile | Weight | Usage |
|---|---:|---:|---:|---|
| Hero display | 110–145px | 70–100px | 900 | Featured promotion. |
| Section display | 80–100px | 55–78px | 900 | Section headlines. |
| Script emphasis | 0.7–1.1× adjacent heading | 0.7–1.0× adjacent heading | 700 | One emotional word or phrase. |
| Menu title | 24–29px | 21–24px | 900 | Dish names. |
| Body large | 16–18px | 14–16px | 500–600 | Hero and section support copy. |
| Body default | 13–14px | 12–13px | 500 | Descriptions and instructions. |
| Button | 13–15px | 12–14px | 800–900 | Actions. |
| Eyebrow | 10–12px | 9–11px | 900 | Section labels and promotion labels. |
| Price | 42–62px | 36–48px | 900 | Hero and product prices. |
| Metadata | 10–12px | 9–11px | 800 | Date, slot, location, and phone details. |

### 5.3 Typography rules

- Use uppercase condensed text for promotional headlines and section titles.
- Use script type only for short accents. Never place a paragraph in script type.
- Use tight line-height between `0.75` and `0.9` for large display headlines.
- Use text shadows only on the main hero headline when needed for poster depth.
- Keep the hero headline to two or three lines maximum on mobile.
- Use strong weight contrast between headlines and supporting copy.
- Do not use more than three typographic voices: condensed display, script accent, and regular utility text.

---

## 6. Layout and Spacing

### 6.1 Content width

- Maximum content width: `1240px`.
- Desktop side padding: `24–32px`.
- Mobile side padding: `18px`.
- Hero text maximum width: `580px`.
- Body copy maximum width: `480px`.
- Collection card width: approximately `360–400px` on desktop.

### 6.2 Spacing scale

Use a 4px base unit.

| Token | Value | Usage |
|---|---:|---|
| `space-1` | 4px | Icon and label micro-gaps. |
| `space-2` | 8px | Badge and metadata spacing. |
| `space-3` | 12px | Button internals and compact card gaps. |
| `space-4` | 16px | Standard card padding. |
| `space-5` | 20px | Card and section sub-gaps. |
| `space-6` | 24px | Mobile page padding and drawer padding. |
| `space-8` | 32px | Header and hero internal spacing. |
| `space-10` | 40px | Component grouping. |
| `space-12` | 48px | Major content separation. |
| `space-16` | 64px | Mobile section spacing. |
| `space-20` | 80px | Desktop section spacing. |
| `space-28` | 112px | Large section padding. |

### 6.3 Borders and radii

The poster variant should use more graphic, structured shapes than the previous soft editorial variant.

| Component | Treatment |
|---|---|
| Primary button | 4–6px radius, not a pill. |
| Secondary text action | No border, direct text and arrow. |
| Menu card | 4–6px radius with a visible border. |
| Collection card | 4–6px radius with blue border and gold offset shadow. |
| Input | 3–5px radius. |
| Avatar ring | Circular, with white and blue rings. |
| Price sticker | Rectangular or angled label with solid offset shadow. |
| Mobile bottom navigation | Square or lightly rounded controls. |
| Modal and drawer | 0–6px radius depending on platform convention. |

Avoid excessive pill-shaped UI. Pills are allowed for compact category filters or status labels, but not every component.

### 6.4 Shadow system

Use hard or semi-hard poster offsets rather than soft luxury shadows.

```css
--shadow-gold-offset: 5px 6px 0 #FFC400;
--shadow-blue-offset: 4px 4px 0 #0C55B0;
--shadow-dark-offset: 6px 7px 0 #071124;
--shadow-drawer: -20px 0 55px rgba(0, 0, 0, 0.35);
```

---

## 7. Owner Illustration and Brand Mark

The illustrated owner is a core identity asset. It should not be treated as a generic avatar.

### 7.1 Approved uses

- Logo/avatar in the header.
- Hero circular identity badge.
- Trust or legacy section.
- Footer brand mark.
- Optional social-sharing card or promotional banner.

### 7.2 Treatment

- Use a circular crop when the illustration is paired with the food hero.
- Use a blue and white ring around the crop.
- Preserve the original illustrated face and clothing colors.
- Avoid placing the avatar on a busy food crop without a ring or backing plate.
- Keep the avatar large enough to be recognizable on mobile.
- Do not distort the image or stretch it outside its aspect ratio.
- If a transparent source becomes available, prefer the transparent asset over a poster crop.

### 7.3 Asset requirements for production

Ask the client for the following if possible:

1. Original transparent character/logo PNG.
2. Original logo in SVG format.
3. High-resolution food image without flyer text.
4. Brand font files or permission to use matching web fonts.
5. Editable source poster if available.
6. Correct phone, location, collection method, and date data.

The current prototype uses a cropped poster avatar as a temporary asset. It should be replaced with a clean source asset before final production.

---

## 8. Page Architecture

The site remains a single-page ordering experience, but each section should resemble a distinct panel in a promotional campaign.

### 8.1 Global order

1. Promotional information strip.
2. Dark navigation header with avatar logo.
3. Poster-style hero promotion.
4. Collection details panel.
5. Friday menu and category filters.
6. Owner-led promise or legacy panel.
7. Three-step ordering process.
8. Final promotional CTA.
9. Dark contact footer.
10. Mobile bottom navigation.

### 8.2 Promotional strip

The top strip may include:

- Promotion date.
- Featured dish.
- Order deadline.
- Phone number.

It should be short, compact, and visibly separate from the header. Do not place full poster copy into the strip.

### 8.3 Header

Required elements:

- Avatar/logo.
- Roti Connect wordmark.
- Menu link.
- Collection link.
- Find my order action.
- Search action if useful.
- Account action if supported.
- Basket action and count.

Desktop header uses a dark navy surface. Mobile header keeps the avatar/logo and basket visible while moving secondary navigation to the fixed bottom bar.

### 8.4 Hero

The hero should contain:

- Eyebrow such as `Friday kitchen drop`.
- Featured dish headline: `Mince Curry roti.`
- Large price: `R45`.
- One-sentence food description.
- Primary action: `Order the special`.
- Secondary action: `Collection details`.
- Date, time, and location proof row.
- Owner illustration within a circular blue/white ring.
- Food image overlapping or adjacent to the owner illustration.
- Gold price sticker or equivalent promotional label.

The hero must not become a literal flyer reconstruction. The action hierarchy must remain obvious and the primary CTA must be visible without scrolling.

### 8.5 Collection panel

The collection panel uses a white or very light surface with a blue top rule and gold secondary rule.

Required information:

- Lunch or dinner availability.
- Collection time.
- Location.
- Pickup slot selector.
- Collection method.
- CTA into the menu.

The collection card should use a navy panel with blue border and gold offset shadow.

### 8.6 Menu panel

Required elements:

- Numbered section label.
- Headline such as `Order the good stuff.`
- Limited-batch cue.
- Category filters.
- Menu cards.
- Add and quantity controls.

Recommended categories:

- Everything.
- Roti specials.
- Roti rolls.
- Curry pots.
- Big plates.

### 8.7 Menu card

Each menu card contains:

| Element | Requirement |
|---|---|
| Image | Warm food crop with consistent aspect ratio. |
| Tag | Gold badge with short promotional label. |
| Category | Blue uppercase metadata. |
| Dish name | Uppercase condensed display. |
| Description | One or two concise sentences. |
| Price | Dark navy or gold-emphasized price. |
| Action | Dark navy add button or quantity control. |

The featured dish should appear first when a promotion is active. Use the same image treatment across cards but allow the featured card to carry a stronger badge.

### 8.8 Promise or legacy panel

This panel introduces the owner illustration and reinforces trust.

Recommended content themes:

- Experience the taste.
- Honour the legacy.
- Small-batch cooking.
- Fair, generous portions.
- Collection made easy.

The owner image should be larger here than in the header and visually supported by circular blue rings.

### 8.9 Ordering steps

Use three numbered cards:

1. Pick your food.
2. Confirm and pay.
3. Collect happy.

Each card should include an icon, title, and one sentence. Follow the cards with an EFT notice.

### 8.10 Footer

The footer should include:

- Avatar/logo.
- Short Windsor Park/Kraaifontein description.
- Phone number.
- Menu link.
- Collection link.
- Find my order action.
- Optional WhatsApp action.

Use the deepest navy surface and gold contact detail.

---

## 9. Interaction and Component Rules

### 9.1 Buttons

Primary buttons are rectangular with a small radius and a hard blue or dark offset shadow.

| Type | Style | Use |
|---|---|---|
| Primary | Gold background, navy text, blue offset shadow | Order, checkout, featured promotion. |
| Dark | Navy background, gold or white text | Add actions, secondary commerce actions. |
| Outline | Transparent background, blue or white border | Secondary navigation or less urgent action. |
| Text action | No border, arrow icon | Informational links and section navigation. |
| Icon-only | Navy/blue surface with visible label or accessible name | Search, close, quantity actions. |

Button minimum height is `44px` on mobile and `46–50px` on desktop.

### 9.2 Category filters

- Use compact rectangular or lightly rounded controls.
- Active state uses electric blue with a small gold offset shadow.
- Allow horizontal scrolling on mobile.
- Expose active state with `aria-selected` or equivalent.
- Do not cause a page reload when filtering.

### 9.3 Basket drawer

The basket drawer should be light paper-white with dark navy text, blue dividers, and gold CTA accents.

Required states:

- Empty basket.
- One item.
- Multiple items.
- Item removed.
- Slot changed.
- Checkout pending.
- Checkout error.

The basket must show:

- Dish name.
- Item price.
- Quantity controls.
- Line total.
- Date.
- Pickup slot.
- Total.
- Collection reminder.

### 9.4 Order lookup modal

The modal should use a paper-white surface, blue border, gold offset shadow, and a navy or gold icon block.

Required elements:

- Visible mobile number label.
- Input field.
- Find order button.
- Loading state.
- No-order-found state.
- Found-order state.
- Explicit placeholder notice if the API is not connected.

### 9.5 Feedback and toasts

Use copy that names the item or action:

- `Mince Curry Roti added`
- `Your collection slot is held for 30 minutes.`
- `Your basket is empty`
- `Ready for checkout`
- `Order lookup is ready`

Do not use vague confirmations such as `Success`.

---

## 10. Responsive Rules

### 10.1 Breakpoints

| Width | Behavior |
|---|---|
| 0–699px | Mobile poster stack, one-column menu, fixed bottom navigation, full-width or near-full-width drawers. |
| 700–979px | Tablet layout, two-column menu, compact hero composition. |
| 980px and above | Two-column poster hero, four-column menu, desktop navigation, overlapping food and avatar art. |

### 10.2 Mobile hero

On mobile:

- Keep the featured headline large, but prevent clipping.
- Stack the text and art rather than squeezing them into two columns.
- Keep price and primary CTA above the fold where possible.
- Place the owner avatar behind or above the food image.
- Keep the gold price sticker visible but not over the main headline.
- Keep date, time, and location in a compact proof row.

### 10.3 Mobile menu cards

Use a compact horizontal card:

- Approximately 39–42% image width.
- Approximately 58–61% content width.
- Title remains readable in uppercase condensed type.
- Description is reduced to one or two lines where necessary.
- Add button stays visible without requiring card expansion.

### 10.4 Mobile bottom navigation

Use four items:

- Home.
- Menu.
- Basket.
- Orders.

The navigation must:

- Remain visible while scrolling.
- Use a dark navy surface.
- Use gold for active state or basket count.
- Not cover page content.
- Have at least 44px touch targets.

### 10.5 Desktop poster composition

On desktop:

- Keep the hero copy on the left and character/food art on the right.
- Use overlapping art and ring frames.
- Let the collection card sit in the right column of the light section.
- Use four menu cards only when descriptions remain readable.
- Keep dark and light sections visually distinct.

---

## 11. Motion and Effects

Motion should feel like a promotional card entering the screen, not like a software dashboard.

### 11.1 Approved effects

- Slight upward reveal for hero copy.
- Slight upward reveal for menu cards.
- Small image scale on card hover.
- Button lift and press compression.
- Basket drawer sliding from the right.
- Modal fade and rise.
- No continuous motion in the owner illustration or food image.

### 11.2 Timing

| Interaction | Duration |
|---|---:|
| Button hover/press | 120–180ms |
| Card hover | 180–240ms |
| Hero entry | 500–700ms |
| Drawer entry | 280–400ms |
| Modal entry | 220–340ms |

Use a strong ease-out curve such as:

```css
--ease-poster: cubic-bezier(0.23, 1, 0.32, 1);
```

### 11.3 Reduced motion

When reduced motion is requested:

- Remove entrance movement.
- Keep color and border feedback.
- Do not animate the large hero image.
- Keep drawers and modals functional with immediate transitions.

---

## 12. Content and Voice

### 12.1 Voice

The voice should be direct, confident, warm, and local.

Use:

- Short promotional statements.
- Specific food language.
- Clear operational information.
- Light colloquial phrasing.
- Memorable lines that can also work on posters and social media.

Avoid:

- Long explanatory paragraphs above the fold.
- Overly formal restaurant language.
- Unverifiable quality claims.
- Excessive punctuation.
- Copy that sounds like a large chain.

### 12.2 Approved headline patterns

| Context | Copy direction |
|---|---|
| Hero eyebrow | `Friday kitchen drop` |
| Hero headline | `Mince Curry roti.` |
| Hero price line | `R45 — a pocket of proper comfort.` |
| Collection headline | `Lunch or dinner. Same big flavour.` |
| Menu headline | `Order the good stuff.` |
| Promise headline | `Experience the taste.` |
| Ordering headline | `From click to curry.` |
| Final CTA | `Bring the appetite. We’ll bring the roti.` |

### 12.3 Date and urgency copy

The ordering deadline and event date must be explicit. The website may use:

- `Order by 03/09`.
- `Friday 04/09`.
- `Available from 11am`.
- `Limited batch — order early`.

Do not create false urgency if the business has not confirmed a limited quantity or deadline.

---

## 13. Accessibility

The bold poster treatment must not reduce usability.

- Use semantic headings in order.
- Provide alt text for food and owner images.
- Use an empty alt attribute for purely decorative background imagery.
- Give all icon-only buttons accessible names.
- Keep visible focus styles in gold or electric blue.
- Do not rely on gold, blue, or white alone to communicate availability or errors.
- Maintain readable contrast on navy panels.
- Use visible labels for date, time, location, phone, and mobile number fields.
- Ensure the basket drawer and order modal trap or manage focus.
- Allow Escape to close overlays.
- Respect reduced-motion preferences.
- Ensure touch targets are at least 44px.
- Ensure the bottom navigation does not obscure content or focus targets.

---

## 14. Technical Implementation Brief

### 14.1 Recommended component structure

```text
AppShell
├── PromotionStrip
├── PosterHeader
├── PosterHero
│   ├── PromotionCopy
│   ├── OwnerBadge
│   ├── FoodPlate
│   └── PriceSticker
├── CollectionSection
│   └── PickupSlotCard
├── MenuSection
│   ├── CategoryTabs
│   ├── MenuGrid
│   └── PosterMenuCard
├── LegacyPromiseSection
├── OrderingSteps
├── PosterFinalCTA
├── PosterFooter
├── MobileBottomNav
├── BasketDrawer
└── OrderLookupModal
```

### 14.2 Suggested content data model

```ts
type Promotion = {
  id: string;
  title: string;
  accentTitle?: string;
  price: number;
  date: string;
  orderDeadline: string;
  availableFrom: string;
  location: string;
  phone: string;
  heroImageUrl: string;
  ownerImageUrl: string;
};

type MenuItem = {
  id: string;
  name: string;
  category: string;
  description: string;
  price: number;
  imageUrl: string;
  tag?: string;
  available: boolean;
  remainingQuantity?: number;
};

type PickupSlot = {
  id: string;
  label: string;
  available: boolean;
};
```

### 14.3 Dynamic data requirements

The following must be configurable by the business owner or a connected backend:

- Featured dish.
- Featured price.
- Promotion date.
- Order deadline.
- Available-from time.
- Collection location.
- Phone number.
- Menu items and prices.
- Pickup slots.
- Availability and sold-out state.
- Collection methods.

### 14.4 Placeholder behavior

If checkout, order lookup, or payment proof upload is not connected:

- Keep the interface visible.
- Show a clear placeholder message.
- Do not show a false order number or payment confirmation.
- Do not claim that a slot is reserved unless the backend has actually reserved it.
- Keep all sensitive payment handling on a secure server-side flow.

### 14.5 Asset performance

- Serve the owner illustration in WebP or optimized PNG where transparency is required.
- Serve food images at appropriate responsive sizes.
- Lazy-load menu images below the hero.
- Keep the first hero asset optimized for mobile.
- Do not use the full square poster as the hero image if it contains text that duplicates live HTML text.
- Use HTML text for all important dates, prices, phone numbers, and CTAs.

---

## 15. QA Checklist

### Visual

- [ ] The page reads as the client’s poster-inspired brand.
- [ ] Navy, blue, gold, and white are consistently applied.
- [ ] The owner illustration is recognizable and not distorted.
- [ ] The hero food image is appetizing and clearly visible.
- [ ] R45 is prominent without overpowering the dish name.
- [ ] The promotional date, deadline, and location are visible.
- [ ] Brush textures remain behind content rather than reducing legibility.
- [ ] Light sections and dark sections have clear separation.
- [ ] The menu card grid is readable on desktop.
- [ ] The mobile layout does not clip the headline or price sticker.

### Functional

- [ ] The hero CTA scrolls to the menu.
- [ ] The collection CTA scrolls to or opens the menu.
- [ ] Pickup slots can be selected.
- [ ] Category tabs filter menu items.
- [ ] Add buttons update the basket count.
- [ ] Quantity controls increment and decrement correctly.
- [ ] Basket drawer opens and closes.
- [ ] Empty basket state provides a menu CTA.
- [ ] Basket total reflects quantities.
- [ ] Order lookup handles loading and not-found states.
- [ ] Collection rules are accessible.
- [ ] Phone number is clickable on mobile using `tel:`.
- [ ] Optional WhatsApp action uses the correct number and message.

### Responsive

- [ ] Test at 320px, 375px, 390px, 768px, 1024px, and 1440px.
- [ ] Test long dish names.
- [ ] Test multiple basket items.
- [ ] Test sold-out items.
- [ ] Test missing hero image fallback.
- [ ] Test reduced motion.
- [ ] Test keyboard navigation.
- [ ] Test modal and drawer Escape behavior.

### Content and operations

- [ ] Date and deadline are current.
- [ ] Price is correct.
- [ ] Collection location is correct.
- [ ] Phone number is correct.
- [ ] Collection start time is correct.
- [ ] Uber Courier wording is operationally accurate.
- [ ] EFT and cash-on-arrival wording is accurate.
- [ ] No unverified promotional claims are displayed.

---

## 16. Production Handoff Notes

The current variant successfully establishes a strong visual direction, but the following assets and decisions should be confirmed before final production:

1. Replace the cropped poster avatar with a clean transparent character/logo file.
2. Confirm whether the business uses `Roti Connect` or `Mince Curry Roti` as the main public-facing name for this promotion.
3. Confirm the live date, deadline, collection hours, phone number, and location.
4. Confirm whether Uber Courier is a real selectable fulfillment option or only promotional wording.
5. Confirm whether the hero food photo represents the featured mince curry roti or should be replaced with a dedicated photo.
6. Confirm the approved script/display font or license a close match.
7. Connect the menu, pickup slots, payment proof, and order lookup to the real order system.

The AI developer should preserve the poster variant’s central identity: **dark navy foundation, electric-blue structure, gold promotional emphasis, white clarity, owner-led illustration, and direct weekly-offer messaging.** Any new page or feature should use the same token system and should look like part of the same promotional campaign.

---

## References

[1]: https://www.w3.org/WAI/standards-guidelines/wcag/ "Web Content Accessibility Guidelines (WCAG)"

[2]: https://fonts.google.com/specimen/Barlow+Condensed "Barlow Condensed font family"
