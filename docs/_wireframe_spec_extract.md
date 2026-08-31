**ROTI CONNECT**

**Mobile ordering wireframe spec**

Build-against document · All 9 screens · Home, Menu and Item sheet
specified to component level

Product: prepaid, capped, collection-only home kitchen --- Kraaifontein,
Cape Town

Audience: engineering + design implementing http://204.168.249.99:8102/

Date: 31 August 2026 · Status: implementation spec, not a visual mock

0\. How to use this spec

1\. Product rules and global system

2\. Screen map and user journeys

3\. Screen 1 --- Home

4\. Screen 2 --- Menu

5\. Screen 3 --- Item sheet

6\. Screen 4 --- Basket

7\. Screen 5 --- Checkout

8\. Screen 6 --- Confirmation / tracker

9\. Screen 7 --- Find my order

10\. Screen 8 --- Account

11\. Screen 9 --- More / Help

12\. Shared components

13\. Build order and acceptance

**0. How to use this spec**

This document is the source of truth for the mobile web app. If a screen
in the live prototype disagrees with this spec, implement the spec.

Each screen section contains: job to be done, ASCII wireframe, component
list, states, keep vs rebuild, data, acceptance checks, and the
benchmark product the pattern is taken from.

Home, Menu and Item sheet are specified to the level you can build this
week. Basket through More are specified to the same skeleton so the rest
of the funnel is not invented later.

**What this product is not**

- Not a DoorDash / Uber Eats marketplace.

- Not an all-day Nando's QSR with dine-in and delivery.

- Not an app-only Starbucks loyalty stack on day one.

It is a weekly-drop kitchen: short menu, pay before cook, 15-minute
collection slots, cap on daily orders.

**1. Product rules and global system**

**Non-negotiable rules**

- One brand name everywhere, including document title and \<title\>:
  Roti Connect. Retire "Brandon's Kitchen" from customer chrome.

- Location and mode before menu: collection only, Kraaifontein, window
  16:00--18:00.

- Prices and stock are edition-specific (this Friday's drop), not a
  permanent catalogue.

- Same-day cut-off 10:00. Advance orders up to 7 days. Slots are 15
  minutes and have capacity.

- Kitchen starts cooking only after EFT is verified, or after staff
  accept a same-day cash order.

- EFT hold is 30 minutes. If unpaid, the slot is released.

- Guest can order and look up an order. Account is for speed the second
  time, not a gate.

- Mobile-first. Desktop is the same flow, wider --- not a second
  magazine site.

**Benchmark map --- steal the pattern, not the cuisine**

  ---------------- --------------------- ---------------------------------
  **Pattern**      **Copy from**         **Do not copy**

  Home = this      Sweetgreen, Domino's  DoorDash restaurant feed
  week's drop      deals                 

  Menu cards +     Nando's ZA, Toast,    100-item curry-house scroll
  category rail    Shake Shack           

  Configure item   Chipotle, CAVA,       A whole extra page
                   Wingstop, Zomato      
                   sheet                 

  Heat / style     Nando's PERi, Behrouz Hidden notes field only
                   Lucknowi/Hyderabadi   

  When to collect  Chick-fil-A, Panera   Uber Eats ASAP + address
                   scheduled pickup      

  After pay        Domino's tracker,     Marketplace driver map
                   Chick-fil-A ready     
                   time                  

  Return visit     Starbucks saved item, Forced account wall
                   Sonic history         

  Guest checkout   Toast, Nando's,       App-only gate
                   McDonald's web        

  Money honesty    DoorDash fee          Cash rules sprung at the door
                   clarity + your Help   
                   copy                  
  ---------------- --------------------- ---------------------------------

**Tab bar --- persistent on every screen except item sheet and success
splash**

+-----------------------------------------------------------------------+
| ┌─────────┬─────────┬─────────┬─────────┬─────────┐                   |
|                                                                       |
| │ Home │ Menu │ Basket │ Account │ More │                             |
|                                                                       |
| │ 🏠 │ 🍽 │ 👜 │ 👤 │ ··· │                                            |
|                                                                       |
| └─────────┴─────────┴─────────┴─────────┴─────────┘                   |
|                                                                       |
| Basket tab shows a badge = item count when cart \> 0.                 |
+-----------------------------------------------------------------------+

Routes: / /order/ /basket/ /account/ /help/

Checkout is /checkout/ and is reached from Basket, not from the tab.
Item sheet is a modal overlay on /order/, not a new tab.

**Visual tokens**

  ----------------- -----------------------------------------------------
  **Token**         **Value**

  Ink               #1A1A1A headings and body

  Muted             #5C5C5C secondary copy

  Accent pink       #9B1B4A selected tab, primary text links, Keep-heat
                    selected chip

  Accent teal       #0E5C66 chips, primary buttons, collection badge

  Paper             #F6F4F1 page background

  Surface           #FFFDF9 cards

  Radius            Cards 16px · pills 999px · buttons 12px

  Type              Headings: source-serif or Georgia. UI: system / Inter
                    / SF.

  Safe area         16px side gutter. Tab bar 56px + iOS home indicator.

  Tap target        Minimum 44×44px. Add buttons and slots never smaller.
  ----------------- -----------------------------------------------------

**Global keep / rebuild from the live prototype**

+-----------------------------------------------------------------------+
| **KEEP**                                                              |
|                                                                       |
| Collection-only model, 15-minute slots with capacity, pay-then-cook,  |
| EFT 30-minute hold.                                                   |
|                                                                       |
| Short Cape menu: roti, gatsby, curry, lasagne.                        |
|                                                                       |
| Bottom tab bar, guest find-order, Help copy (best-written screen      |
| today).                                                               |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **REBUILD**                                                           |
|                                                                       |
| One brand name. One visual system (mobile app, not magazine + flyer + |
| type-list).                                                           |
|                                                                       |
| Photo on every sellable item. Item sheet. Sticky basket bar.          |
|                                                                       |
| Slot picker only after food is in the basket. Tracker after           |
| place-order.                                                          |
|                                                                       |
| Home category tiles that are real links. Flyer price matching the     |
| menu.                                                                 |
+-----------------------------------------------------------------------+

**2. Screen map and user journeys**

**Primary journey --- first order**

Home → tap hero or category → Menu → tap item → Item sheet → Add →
sticky bar → Basket (pick day + slot) → Checkout (details + EFT/cash) →
Confirmation tracker.

**Return journey**

Home → Repeat last order (Account or Home module) → Basket with items
prefilled → confirm slot → Checkout.

**Collection journey**

SMS / WhatsApp link or Home "Find my order" → Lookup → Tracker (status +
address + I've paid).

**Information architecture**

  ------------------ ------------------ ---------------------------------
  **Screen**         **Route**          **Purpose**

  1 Home             /                  Sell this week's drop; route to
                                        menu or lookup

  2 Menu             /order/            Scan 8--12 items; add in two taps

  3 Item sheet       overlay on /order/ Heat, extras, notes, add with
                                        live price

  4 Basket           /basket/           Quantities + day + 15-min slot

  5 Checkout         /checkout/         Name, phone, EFT or cash, place
                                        order

  6 Tracker          /order/:id         Status, collect time, pay
                                        reference

  7 Find order       /lookup/           Guest status via order no. +
                                        phone

  8 Account          /account/          OTP login, last order, saved
                                        mobile

  9 More / Help      /help/             Cut-off, slots, pay rules,
                                        address
  ------------------ ------------------ ---------------------------------

**3. Screen 1 --- Home**

Job: sell this week's drop and get a returning customer to reorder or
find an order. Benchmark: Sweetgreen (one job above the fold), Domino's
(deal then reorder), Nando's ZA (mode visible before menu), Starbucks
(last item as a saved object).

**Wireframe --- first visit, phone 390×844**

+-----------------------------------------------------------------------+
| ROTI CONNECT                                                          |
|                                                                       |
| ─────────────────────────────────────────────────────                 |
|                                                                       |
| ( teal chip ) Collection only · Fri 4 Sep · 16:00--18:00              |
|                                                                       |
| Order by Wed 3 Sep, 10:00                                             |
|                                                                       |
| ┌─────────────────────────────────────────────┐                       |
|                                                                       |
| │ THIS FRIDAY │                                                       |
|                                                                       |
| │ \[ photo: chicken roti \] │                                         |
|                                                                       |
| │ │                                                                   |
|                                                                       |
| │ Chicken roti R45 │                                                  |
|                                                                       |
| │ Kraaifontein · lunch or dinner │                                    |
|                                                                       |
| │ │                                                                   |
|                                                                       |
| │ \[ Order this drop \] │                                             |
|                                                                       |
| └─────────────────────────────────────────────┘                       |
|                                                                       |
| Entire card is also a tap target → /order/?featured=chicken-roti      |
|                                                                       |
| Already ordered? \[ Find my order \]                                  |
|                                                                       |
| What are you hungry for?                                              |
|                                                                       |
| ┌──────────────┐ ┌──────────────┐                                     |
|                                                                       |
| │ photo │ │ photo │                                                   |
|                                                                       |
| │ Roti │ │ Gatsby │                                                   |
|                                                                       |
| │ from R65 │ │ from R95 │                                             |
|                                                                       |
| └──────────────┘ └──────────────┘                                     |
|                                                                       |
| ┌──────────────┐ ┌──────────────┐                                     |
|                                                                       |
| │ photo │ │ photo │                                                   |
|                                                                       |
| │ Curry │ │ Lasagne │                                                 |
|                                                                       |
| │ from R85 │ │ from R90 │                                             |
|                                                                       |
| └──────────────┘ └──────────────┘                                     |
|                                                                       |
| How collection works \[ 3 steps, compact \]                           |
|                                                                       |
| 1 Choose a slot 2 Pay EFT 3 Text on arrival                           |
|                                                                       |
| ┌─────────┬─────────┬─────────┬─────────┬─────────┐                   |
|                                                                       |
| │ Home \* │ Menu │ Basket │ Account │ More │                          |
|                                                                       |
| └─────────┴─────────┴─────────┴─────────┴─────────┘                   |
+-----------------------------------------------------------------------+

**Wireframe --- returning visit (has last order)**

+-----------------------------------------------------------------------+
| ... chip + hero as above ...                                          |
|                                                                       |
| Your last order                                                       |
|                                                                       |
| ┌─────────────────────────────────────────────┐                       |
|                                                                       |
| │ 2× Chicken roti · Medium │                                          |
|                                                                       |
| │ Collected Fri 28 Aug │                                              |
|                                                                       |
| │ \[ Repeat order \] │                                                |
|                                                                       |
| └─────────────────────────────────────────────┘                       |
|                                                                       |
| What are you hungry for? ...tiles...                                  |
+-----------------------------------------------------------------------+

**Components**

  ------------------ ----------------------------------------------------
  **Component**      **Behaviour**

  Brand header       Plain wordmark. No hamburger. Tabs do the
                     navigation.

  Collection chip    Always visible. Tapping opens a 1-screen sheet:
                     address, window, cut-off, no-hooting rule.

  Cut-off line       Computed from next edition. If cut-off passed, copy
                     becomes "Ordering for next Friday".

  Hero drop card     Photo, item name, price matching menu, area, primary
                     button under the photo --- never over the location.

  Find my order      Secondary button → /lookup/.

  Category tiles     2×2. Photo + name + from-price. Tap → /order/#roti
                     etc. Never empty colour blocks.

  How it works       3 compact steps. Not a novel. Link "Read the rules"
                     → /help/.

  Repeat module      Only if device has lastOrderId or logged-in history.
                     Prefills basket, does not skip slot pick.

  Search             Remove from Home. Ten items do not need it. Search
                     lives as a filter on Menu if at all.
  ------------------ ----------------------------------------------------

**Keep vs rebuild (Home)**

Keep: tab bar, collection-only chip, one hero drop, Find my order as
second action.

Rebuild: empty teal/maroon tiles; Order now overlapping Kraaifontein;
flyer R45 vs menu R65; search above the only CTA; two visual languages
vs desktop magazine.

**States**

  ----------------- -----------------------------------------------------
  **State**         **What the user sees**

  Default           Next edition hero + 4 category tiles + how-it-works.

  Cut-off passed    Hero still sells the food but CTA is "Order for Fri
                    11 Sep". Same-day slots hidden later in basket.

  Sold out edition  Hero badge "Sold out". CTA becomes "See next week" or
                    notify.

  Returning         Repeat last order module between hero and tiles.

  Has live order    Slim banner under chip: "Order #RC-1847 · Ready 16:15
                    · View".
  ----------------- -----------------------------------------------------

**Acceptance --- Home**

- No control is covered by another control. Location text on the flyer
  is fully readable.

- Each category tile has a visible label, from-price, and a hit area ≥
  44px tall.

- Hero price equals the featured menu item price.

- Find my order reaches /lookup/.

- Tab bar does not cover the last tile. Page padding-bottom ≥ 72px.

**4. Screen 2 --- Menu**

Job: scan 8--12 items and add one in two taps. Benchmark: Nando's ZA
(photo cards + category rail), Toast (independent-restaurant card),
Sweetgreen / Shake Shack (short menu), Behrouz (protein × format as the
spine).

**Wireframe**

+-----------------------------------------------------------------------+
| ROTI CONNECT                                                          |
|                                                                       |
| ─────────────────────────────────────────────────────                 |
|                                                                       |
| Collection · Fri 4 Sep · 16:00--18:00                                 |
|                                                                       |
| \[ All \] \[ This week \] \[ Roti \] \[ Gatsby \] \[ Curry \] \[      |
| Lasagne \]                                                            |
|                                                                       |
| ← sticky horizontal chips, current = All                              |
|                                                                       |
| THIS WEEK                                                             |
|                                                                       |
| ┌──────┬──────────────────────────────────────────┐                   |
|                                                                       |
| │ img │ Chicken roti THIS WEEK│                                       |
|                                                                       |
| │ │ Chips, masala chicken, rolled tight │                             |
|                                                                       |
| │ │ Serves 1 │                                                        |
|                                                                       |
| │ │ R45 \[ + \] │                                                     |
|                                                                       |
| └──────┴──────────────────────────────────────────┘                   |
|                                                                       |
| ROTI ROLLS                                                            |
|                                                                       |
| ┌──────┬──────────────────────────────────────────┐                   |
|                                                                       |
| │ img │ Chicken masala roti │                                         |
|                                                                       |
| │ │ Chips, chicken, rolled tight · Serves 1 │                         |
|                                                                       |
| │ │ R65 \[ + \] │                                                     |
|                                                                       |
| └──────┴──────────────────────────────────────────┘                   |
|                                                                       |
| ┌──────┬──────────────────────────────────────────┐                   |
|                                                                       |
| │ img │ Steak masala roti │                                           |
|                                                                       |
| │ │ R70 \[ + \] │                                                     |
|                                                                       |
| └──────┴──────────────────────────────────────────┘                   |
|                                                                       |
| CURRY · GATSBY · LASAGNE (same card)                                  |
|                                                                       |
| ┌─────────────────────────────────────────────────┐                   |
|                                                                       |
| │ 1 item · R45 View basket → │ sticky                                 |
|                                                                       |
| └─────────────────────────────────────────────────┘                   |
|                                                                       |
| ┌─────────┬─────────┬─────────┬─────────┬─────────┐                   |
|                                                                       |
| │ Home │ Menu \* │ Basket¹ │ Account │ More │                         |
|                                                                       |
| └─────────┴─────────┴─────────┴─────────┴─────────┘                   |
+-----------------------------------------------------------------------+

**Menu data to ship (single source of truth)**

  -------------- -------------- ----------- ---------------------------------
  **Item**       **Category**   **Price**   **Notes**

  Chicken roti   this-week      R45         Must match Home hero. Badge THIS
  (drop)                                    WEEK.

  Chicken masala roti           R65         Serves 1. Default heat Medium.
  roti roll                                 

  Steak masala   roti           R70         Serves 1.
  roti roll                                 

  Chicken curry  curry          R85         Serves 1.
  & roti                                    

  Steak curry &  curry          R95         Serves 1.
  roti                                      

  Chicken masala gatsby         R95         Item copy: feeds 2--4. Not a
  gatsby                                    category label.

  Steak masala   gatsby         R100        Feeds 2--4.
  gatsby                                    

  Full house     gatsby         R130        Egg + cheese. Feeds 2--4.
  steak gatsby                              

  Chicken roti & gatsby         R110        Combo. Do not invent a fifth
  gatsby                                    cuisine.

  Steak roti &   gatsby         R115        Combo.
  gatsby                                    

  Beef lasagne   lasagne        R90         Serves 1. Weekly extra.
  -------------- -------------- ----------- ---------------------------------

**Components**

  ------------------ ----------------------------------------------------
  **Component**      **Behaviour**

  Category chips     Sticky under header. Tap filters and scrolls to the
                     section. Deep-link /order/#gatsby from Home tiles.

  Item card          72×72 photo, name, one-line description, serves,
                     price, + button. Whole row opens the item sheet. +
                     opens the sheet too (same place).

  Sold-out card      40% photo opacity, badge Sold out, + disabled.

  Sticky basket bar  Appears only when cartCount \> 0. "N items · Rxx
                     View basket". Sits above the tab bar.

  Sample banner      Remove from customer UI. If needed, show only when
                     ?preview=1 for Brandon.

  Day / slot picker  Not on this screen. Move to Basket.
  ------------------ ----------------------------------------------------

**Keep vs rebuild (Menu)**

Keep: short menu, category names, one-line descriptions, serves-N (on
the item).

Rebuild: "SAMPLE MENU" on a live screen; text-only rows; 28px Add; slots
mixed into browse; Gatsby "Serves 4" as a category heading.

**Acceptance --- Menu**

- Every item has a photo, price, and 44px add target.

- No slot picker and no R0.00 footer on this screen.

- Adding an item opens the item sheet; after confirm, sticky bar shows
  count and total.

- Home category tiles land on the matching chip + section.

**5. Screen 3 --- Item sheet**

Job: configure heat / extras / notes and add, with a live price. This
screen does not exist in the prototype --- build it. Benchmark: Chipotle
and CAVA (required choices first), Wingstop (chips not paragraphs),
Behrouz (mild vs spicy as identity), Zomato / Uber Eats / Grab (bottom
sheet, pinned add bar).

**Wireframe**

+-----------------------------------------------------------------------+
| ──── drag handle ────                                                 |
|                                                                       |
| Chicken masala roti \[ x \]                                           |
|                                                                       |
| ┌─────────────────────────────────────────────┐                       |
|                                                                       |
| │ item photo │                                                        |
|                                                                       |
| └─────────────────────────────────────────────┘                       |
|                                                                       |
| R65 · Serves 1                                                        |
|                                                                       |
| Chips, masala chicken, roti, rolled tight.                            |
|                                                                       |
| Heat Required                                                         |
|                                                                       |
| \[ Mild \] \[ Medium \* \] \[ Hot \]                                  |
|                                                                       |
| Extra roti Optional                                                   |
|                                                                       |
| \[ No \* \] \[ Yes +R12 \]                                            |
|                                                                       |
| Chips Optional                                                        |
|                                                                       |
| \[ With chips \* \] \[ No chips −R5 \]                                |
|                                                                       |
| Notes                                                                 |
|                                                                       |
| ┌─────────────────────────────────────────────┐                       |
|                                                                       |
| │ e.g. chilli on the side │                                           |
|                                                                       |
| └─────────────────────────────────────────────┘                       |
|                                                                       |
| ┌─────────────────────────────────────────────┐                       |
|                                                                       |
| │ Add · R65 │                                                         |
|                                                                       |
| └─────────────────────────────────────────────┘                       |
+-----------------------------------------------------------------------+

**Modifier rules**

  ---------------- --------------- ---------------------------------------
  **Modifier**     **Required?**   **Rules**

  Heat             Yes             Mild / Medium / Hot. Default Medium.
                                   Add disabled until chosen (preselect
                                   Medium so Add is enabled on open).

  Extra roti       No              No / Yes +R12. Default No. Live price
                                   on the button.

  Chips            No              With chips / No chips −R5 where the
                                   item includes chips. Hide on lasagne
                                   and curry-only plates.

  Notes            No              Max 80 characters. No second page.

  Qty              Yes             If editing from basket, show − / qty /
                                   +. On first add, qty = 1. Repeat adds
                                   increment after matching modifiers.
  ---------------- --------------- ---------------------------------------

**Behaviour**

- Present as a bottom sheet over Menu. Dimmed backdrop tap or X
  dismisses without adding.

- Primary button label is "Add · R{live}". When opened from Basket Edit:
  "Update · R{live}".

- On Add: close sheet, increment cart, toast "Added · View basket", show
  sticky bar.

- Do not navigate to Basket automatically after one add. People often
  add a second item.

**Keep vs rebuild (Item sheet)**

Keep: nothing on-device. The need (heat, extra roti, no chips, notes) is
real.

Rebuild: current Add that goes nowhere. Do not invent a full-page
product route for a 10-item menu.

**Acceptance --- Item sheet**

- Price on the button updates when extras change.

- Add writes {itemId, heat, extras\[\], notes, qty, unitPrice,
  lineTotal} into the cart.

- Sheet is usable on a 390-wide screen without trapping scroll behind
  the tab bar.

**6. Screen 4 --- Basket**

Job: confirm items, then pick day and a 15-minute slot. Benchmark:
Chick-fil-A and Panera (time before pay), Domino's (running total),
DoorDash (modifiers under the name).

**Wireframe --- filled**

+-----------------------------------------------------------------------+
| Your order                                                            |
|                                                                       |
| ─────────────────────────────────────────────────────                 |
|                                                                       |
| Chicken roti · Medium                                                 |
|                                                                       |
| Extra roti                                                            |
|                                                                       |
| \[ − \] 1 \[ + \] Edit R57                                            |
|                                                                       |
| Add an extra roti to the table? +R12                                  |
|                                                                       |
| Collect                                                               |
|                                                                       |
| \[ Today 31 \] \[1\] \[2\] \[3\] \[ Fri 4 \* \] \[5\] \[6\] \[7\]     |
|                                                                       |
| Window 16:00--18:00 · Kraaifontein                                    |
|                                                                       |
| \[ 16:00 12 left \] \[ 16:15 3 left \]                                |
|                                                                       |
| \[ 16:30 FULL \] \[ 16:45 8 left \]                                   |
|                                                                       |
| \[ 17:00 10 left \] \[ 17:15 9 left \]                                |
|                                                                       |
| \[ 17:30 11 left \] \[ 17:45 7 left \]                                |
|                                                                       |
| Subtotal R57                                                          |
|                                                                       |
| \[ Continue · R57 \] disabled until a slot is picked                  |
+-----------------------------------------------------------------------+

**Wireframe --- empty**

+-----------------------------------------------------------------------+
| No order yet                                                          |
|                                                                       |
| Friday's menu is short. Start with the chicken roti.                  |
|                                                                       |
| \[ See the menu \]                                                    |
+-----------------------------------------------------------------------+

**Rules**

- Empty state never shows Total R0.00 or Place order.

- Continue is disabled until cartCount \> 0 AND a slot with remaining
  capacity is selected.

- FULL slots are visible but not tappable.

- Same-day tab hidden or disabled after 10:00.

- Repeat order lands here with items filled and slot unselected.

**Keep vs rebuild (Basket)**

Keep: 15-minute slots with capacity --- this is the operational edge.
Help already explains it.

Rebuild: basket as a R0 strip on the menu; empty Collect / Window on
checkout; no steppers.

**Acceptance --- Basket**

- Slot capacity displayed as "N left" or FULL.

- Edit reopens the item sheet in update mode.

- Tab badge equals sum of quantities.

**7. Screen 5 --- Checkout**

Job: take name, phone, and pay method, then place. Benchmark: DoorDash
(fulfilment above payment, honest costs), Starbucks (saved details),
your own Help page (EFT 30-min hold).

**Wireframe**

+-----------------------------------------------------------------------+
| Checkout                                                              |
|                                                                       |
| ─────────────────────────────────────────────────────                 |
|                                                                       |
| Collect Fri 4 Sep · 16:15--16:30                                      |
|                                                                       |
| Kraaifontein · text on arrival, do not hoot                           |
|                                                                       |
| \[ Change slot \]                                                     |
|                                                                       |
| Your details                                                          |
|                                                                       |
| Name \[ \]                                                            |
|                                                                       |
| Mobile \[ 07 \]                                                       |
|                                                                       |
| \[ \] Save on this phone                                              |
|                                                                       |
| Pay                                                                   |
|                                                                       |
| ( • ) EFT --- we hold the slot 30 minutes                             |
|                                                                       |
| ( ) Cash --- same day only, we must accept it                         |
|                                                                       |
| Chicken roti ×1 · Medium + extra roti R57                             |
|                                                                       |
| Total R57                                                             |
|                                                                       |
| We cook after EFT clears. Cash is confirmed by us.                    |
|                                                                       |
| \[ Place order \]                                                     |
+-----------------------------------------------------------------------+

**Rules**

- If Collect/Window is empty, redirect to Basket. Never show "Collect
  ---".

- Place order disabled until name, valid SA mobile, pay method, and a
  live slot.

- Cash option hidden when selected day is not today, or when kitchen has
  disabled cash.

- On Place order (EFT): create order status=held, start 30-min timer, go
  to Tracker with payment reference.

- On Place order (Cash): status=pending_staff. Tracker says "Waiting for
  the kitchen to accept".

- Do not fake card rails if Brandon is on EFT.

**Keep vs rebuild (Checkout)**

Keep: two-step mental model; EFT + limited cash; 30-min hold concept.

Rebuild: Brandon's Kitchen title; empty Collect/Window; Place order on
an empty cart; missing name/phone fields.

**Acceptance --- Checkout**

- Fulfilment block is complete before payment options.

- EFT 30-min hold is visible on this screen, not only on Help.

**8. Screen 6 --- Confirmation / tracker**

Job: a page people can screenshot into the family WhatsApp. Benchmark:
Domino's Pizza Tracker, Chick-fil-A ready time. Do not build a courier
map.

**Wireframe**

+-----------------------------------------------------------------------+
| Order #RC-1847                                                        |
|                                                                       |
| ─────────────────────────────────────────────────────                 |
|                                                                       |
| ● Held --- waiting for EFT                                            |
|                                                                       |
| ○ Confirmed                                                           |
|                                                                       |
| ○ Cooking                                                             |
|                                                                       |
| ○ Ready · 16:15                                                       |
|                                                                       |
| ○ Collected                                                           |
|                                                                       |
| Pay to \[bank name\]                                                  |
|                                                                       |
| Acc \[number\]                                                        |
|                                                                       |
| Ref RC1847 \[ Copy \]                                                 |
|                                                                       |
| Amount R57                                                            |
|                                                                       |
| Slot held until 18:33                                                 |
|                                                                       |
| Collect 16:15--16:30                                                  |
|                                                                       |
| \[ pin / address, Kraaifontein \]                                     |
|                                                                       |
| Text when you are outside. Do not hoot.                               |
|                                                                       |
| Chicken roti ×1 · Medium + extra roti                                 |
|                                                                       |
| \[ I've paid \] \[ WhatsApp the kitchen \]                            |
+-----------------------------------------------------------------------+

**Status machine**

  ----------------- -----------------------------------------------------
  **Status**        **Meaning**

  held              EFT order created. Slot reserved 30 min. Show bank
                    details.

  pending_staff     Cash order waiting for kitchen accept.

  confirmed         Money seen or cash accepted. Not cooking yet.

  cooking           Kitchen has started. Optional "started at" timestamp.

  ready             Ready for collection. Highlight the slot.

  collected         Done. Offer Repeat next week.

  released          EFT not paid in 30 min. Slot freed. CTA: Re-order.

  cancelled         Staff or customer cancelled. Point to Help policy.
  ----------------- -----------------------------------------------------

**Keep vs rebuild (Tracker)**

Keep: the operational truth already written on Help (cook after pay,
15-min window).

Rebuild: this screen is missing. After Place order the user must not
land on Home or an empty basket.

**Acceptance --- Tracker**

- Order id, status, slot, address rule, and pay reference all visible
  without scrolling past one screen on a standard phone, or with a
  single short scroll.

- I've paid notifies the kitchen; it does not mark confirmed by itself.

- Find-order lookup opens this same view, not a second layout.

**9. Screen 7 --- Find my order**

Job: guest recovery. Benchmark: Domino's track-by-phone. Keep the
two-field form that already exists at /lookup/.

**Wireframe**

+-----------------------------------------------------------------------+
| Find your order                                                       |
|                                                                       |
| ─────────────────────────────────────────────────────                 |
|                                                                       |
| Order number \[ RC-1847 \]                                            |
|                                                                       |
| Mobile used \[ 07 \]                                                  |
|                                                                       |
| \[ Find my order \]                                                   |
|                                                                       |
| Need help? How collection works →                                     |
+-----------------------------------------------------------------------+

**Rules**

- Both fields required. Normalise order ids (rc1847 = RC-1847).

- Match order number AND last 9 digits of the phone on the order.

- Success → /order/RC-1847 (tracker). Failure → "No order with that
  number and phone." + link to WhatsApp.

- Home "Find my order" and Account guest link both use this screen.

**Keep vs rebuild**

Keep: guest lookup, order no. + phone, no account required.

Rebuild: style it into the same visual system; success must be the
tracker, not a different page.

**Acceptance**

- A known pair returns the tracker. A bad pair does not leak whether the
  order id exists.

**10. Screen 8 --- Account**

Job: phone login, saved details, last order. Benchmark: Starbucks
(account = reorder list), Sonic (history easy to find), Chipotle (guest
can still order).

**Wireframe --- logged out**

+-----------------------------------------------------------------------+
| Your account                                                          |
|                                                                       |
| Save details and repeat last Friday's order.                          |
|                                                                       |
| Mobile \[ 07 \]                                                       |
|                                                                       |
| \[ Send code \]                                                       |
|                                                                       |
| Guest? Find an order without logging in →                             |
+-----------------------------------------------------------------------+

**Wireframe --- logged in**

+-----------------------------------------------------------------------+
| Hi Thabo                                                              |
|                                                                       |
| Next collection Fri 4 Sep · 16:15                                     |
|                                                                       |
| Last order                                                            |
|                                                                       |
| 2× Chicken roti · Medium                                              |
|                                                                       |
| \[ Repeat \]                                                          |
|                                                                       |
| Saved mobile 07x xxx xxxx                                             |
|                                                                       |
| \[ Log out \]                                                         |
+-----------------------------------------------------------------------+

**Rules**

- OTP to mobile only. No email/password in v1.

- First order must work as guest. Account is optional.

- Repeat prefills basket; user still picks a slot.

**Keep vs rebuild**

Keep: phone-first, guest path, "find order without logging in".

Rebuild: dead login/signup links; account that does not show last order.

**Acceptance**

- OTP path creates a session and returns to Home or the screen that sent
  them here.

- Logged-in Home shows the Repeat module.

**11. Screen 9 --- More / Help**

Job: operational truth in four cards, not a novel. The live Help copy is
the best writing in the product --- keep the facts, rebuild the layout.
Benchmark: Sweetgreen / Pret short rules.

**Wireframe**

+-----------------------------------------------------------------------+
| How it works                                                          |
|                                                                       |
| ─────────────────────────────────────────────────────                 |
|                                                                       |
| ┌─────────────────────────────────────────────┐                       |
|                                                                       |
| │ Order by 10:00 for the same day │                                   |
|                                                                       |
| │ Or any open day up to 7 days ahead │                                |
|                                                                       |
| └─────────────────────────────────────────────┘                       |
|                                                                       |
| ┌─────────────────────────────────────────────┐                       |
|                                                                       |
| │ Collect 16:00--18:00 · 15-minute slot │                             |
|                                                                       |
| │ Full slots disappear. Check your confirmation│                      |
|                                                                       |
| └─────────────────────────────────────────────┘                       |
|                                                                       |
| ┌─────────────────────────────────────────────┐                       |
|                                                                       |
| │ We cook after EFT clears (30 min hold) │                            |
|                                                                       |
| │ Cash: same day only, if we accept it │                              |
|                                                                       |
| └─────────────────────────────────────────────┘                       |
|                                                                       |
| ┌─────────────────────────────────────────────┐                       |
|                                                                       |
| │ Kraaifontein · text on arrival · no hooting │                       |
|                                                                       |
| └─────────────────────────────────────────────┘                       |
|                                                                       |
| Policies → WhatsApp the kitchen →                                     |
+-----------------------------------------------------------------------+

**Keep vs rebuild**

Keep almost all of the content: 10:00 cut-off, 7 days ahead, 15-min
capacity, cook-after-payment, EFT 30-min, cash same-day, policies link.

Rebuild: "Brandon's Kitchen" title; wall of markdown as the first view.
Surface the four facts on Home and Checkout as one-liners too.

**Acceptance**

- A first-time user can answer "when do I pay, when do I collect, where"
  from this screen alone.

**12. Shared components**

**Sticky basket bar**

Visible on Menu (and Home if cart \> 0). Sits 8px above the tab bar.
Label: "{n} item(s) · R{total} View basket". Tap → /basket/.

**Cart line item shape**

id, itemId, name, heat, extras\[\], notes, qty, unitPrice, lineTotal,
photoUrl.

**Edition object**

id, label (Friday 4 Sep), orderBy (Wed 3 Sep 10:00), windowStart,
windowEnd, slots\[{start, capacity, remaining}\], featuredItemId,
soldOut.

**Toasts**

Added, Slot no longer available, Payment hold expired. Never blocking
modals for success.

**Errors**

- Network: retry on the same screen.

- Slot taken between basket and checkout: return to Basket with that
  slot marked FULL and a message.

- OTP failed: resend after 30s.

**13. Build order and acceptance**

**Sequence**

  --------- -------------------------------------------------------------
  **\#**    **Ship this**

  **1**     Rename every customer-facing string and \<title\> to Roti
            Connect. Kill Brandon's Kitchen in chrome.

  **2**     Home: real category tiles, flyer CTA under the photo, hero
            price = menu price, padding above tab bar.

  **3**     Menu cards with photos, sticky chips, remove sample banner
            and slot picker.

  **4**     Item sheet with heat / extras / live price.

  **5**     Basket with steppers, day + slot capacity, empty state.

  **6**     Checkout with name, phone, EFT/cash, no empty Collect.

  **7**     Tracker + wire Find my order to the same view.

  **8**     Account OTP + Repeat last order.

  **9**     Help as four cards. One-liners reused on Home and Checkout.
  --------- -------------------------------------------------------------

**Definition of done for v1**

- A guest can go Home → featured roti → configure Medium → add → pick
  Fri 16:15 → enter name and phone → place EFT order → see reference
  RC-xxxx.

- A second device can recover that order via Find my order.

- After 10:00, Today is not offered.

- A FULL slot cannot be selected.

- No screen shows Brandon's Kitchen.

- No empty colour tiles on Home.

Screens 1--6 are the product. Screens 7--9 are trust. Do not polish
Account before the tracker exists.

**Out of scope for v1**

- Delivery, card gateway, multi-kitchen, loyalty points, desktop
  magazine layout as a separate product.
