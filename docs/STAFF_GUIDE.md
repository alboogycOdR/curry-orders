# Roti Connect — Staff Order Management Guide

This guide explains every screen a Roti Connect staff member uses, in roughly the order you'll touch them during a normal service day. It was rewritten on 2026-09-14 by reading the live code (`src/staff/`, `src/core/`, and every staff screen template) rather than copying the previous draft, so every button label, URL and status change below matches what is actually on screen today. If you spot something on screen that doesn't match this guide, trust the screen and tell the developer — the system does get updated.

**Two servers are currently live.** Staff may be pointed at either one — ask if you're not sure which one you should be using:

- Production: `http://204.168.249.99:8102/manage/...`
- Newer "poster" version: `http://204.168.249.99:8105/manage/...`

Every URL in this guide is written as a path starting `/manage/...` — put whichever base above in front of it.

---

## Getting in

**Login page:** `/manage/login/`

The login page asks for your **Email** and **Password** — not a username. (An earlier version of this guide said "username"; the field is your email address.)

1. Go to `/manage/login/`.
2. Type your email address and password.
3. Click **Log in**.

You land on the **Inbox** afterwards (or wherever you were trying to go, if you followed a link that sent you to login first).

**Other ways to sign in**, both shown on the login page itself:

- **Sign in with Google** — a button above the password form. This only works if your Google account's email has been added to the staff allow-list by an admin; if it hasn't, you'll see "Your Google account is not authorised as staff. Contact the owner."
- **Sign in by email link instead** — a link below the form, goes to `/manage/auth/email/`. Enter your staff email address and, if it's on the allow-list, you'll be sent a one-time sign-in link (no password needed). For security the page always says a link was sent, even if your email isn't recognised — if you don't get an email, double check the address or ask the owner to add you.

**If you get locked out:** after too many wrong password attempts, the account locks for **15 minutes**. The login page will tell you this and say to contact the owner if you need in sooner.

**Temporary passwords:** if the owner has just set you up (or reset your password), you'll be forced straight to a **"Set a new password"** screen the first time you log in — you can't skip this and go straight to the Inbox. New passwords must be at least **10 characters**.

**Getting back here from the public website:** on a phone, tap **More** in the bottom nav, then **Kitchen staff login**. On a wider screen while logged out, there's a small **Staff login** link in the site footer.

**Once logged in**, look for the **Staff** dropdown in the top-right of every page (next to the Order/Basket icons) — it's your menu for every staff screen from here on: Inbox, Calendar, Kitchen desk, Collection, Payments, Cash, Daily controls, Menu editor, New assisted order, and (owners only) Settings, plus **Log out** at the bottom.

---

## Screen 1 — Inbox (`/manage/`)

The landing page after login, and your morning briefing. It pulls together everything across the whole system that might need attention *right now*, in five sections, each shown only if it has something in it. If every section is empty you'll see a plain "Inbox is clear — nothing needs attention right now."

### The five sections

| Section | What's in it |
|---|---|
| **Cash requests** | Every order a customer placed choosing to pay cash on collection, still waiting for you to accept or reject it. Same list as the dedicated Cash screen. |
| **Hold lapsed / SLA breached** | EFT orders whose payment hold has already run out with no proof uploaded, *and* orders sitting in "payment review" longer than the settings-configured review window (15 minutes by default). Both need a decision on the Payments screen. |
| **Orders with notes** | Any still-open order (not yet collected/cancelled/expired) carrying a customer note — most recent 30. Check these for dietary requirements or special requests before they reach the kitchen. |
| **Recent assisted** | The last 20 orders staff created on the customer's behalf (phone, WhatsApp, in-person) — shown for reference/follow-up, not for action. |
| **Recently expired** | Orders whose EFT hold expired in the last 48 hours, with a **Reinstate** option in case the customer still wants to pay. |

### What each row shows and what you can do with it

Every row shows the order number (a link that opens the customer's own order-status page in a new tab — there's no separate staff order-detail page), the customer's name with a **WhatsApp** link straight to them (when a mobile number is on file), the collection day/slot, the status (plus the note text, if any), who it's assigned to, and a row of action buttons:

- **Assign to me / Unassign** — every row has this. Click it to put your name against the order (useful for "I'm handling this one"); click again to take your name back off. This is just a label, not a status change — nothing else on the order changes.
- **Accept / Reject** — cash-request rows only. Accept moves the order to `cash_due` (it then appears on the Kitchen desk); Reject cancels it and frees up its slot.
- **Reinstate** — recently-expired rows only. Asks for a reason (a text box appears), then puts the order back into "Awaiting EFT" with a brand new payment hold, so the customer can pay again. This only works if the day/slot/dishes still have room — if capacity has since filled up, it will fail with a capacity error rather than push the order back in.
- **Move to… / Move** — a dropdown of that day's other open slots plus a **Move** button, shown wherever the order still has other slots to move to. Changes the order's collection slot without changing anything else about it.

If any button fails (the order changed status in the meantime, for example — someone else already actioned it), the row shows "Action failed — reload the page to check this order's current status." rather than silently doing nothing.

---

## Screen 2 — Calendar (`/manage/calendar/`)

An 8-day grid (today plus the next 7 days) showing how full each day is at a glance. Each day is a clickable card that takes you straight to that day's **Daily controls** screen (below) to make changes.

Each card shows:

- The date, and an **Open** / **Closed** badge for whether the day is taking orders at all.
- **Orders: X / Y** — how many orders are booked against that day's order cap.
- **Cash: X / Y** — how many of those are cash orders, against the cash cap for the day.
- A row of small coloured bars, one per collection slot, showing how full each slot is — hover over a bar to see the exact time and occupancy. Colours: grey = empty, light green = under 50% full, yellow = 50–89% full, orange = 90%+ full.
- A **⚠ warning line** for any dish that's at 80% or more of its daily unit cap for that day (e.g. "⚠ Chicken Masala Roti Roll: 16/20 — cap or mark unavailable") — a heads-up that you may want to close it out via Daily controls before it oversells.

Use this screen to spot a day that's filling up, or a dish that's about to run out, before it becomes a problem — then click through to Daily controls to actually act on it.

---

## Screen 3 — Kitchen desk (`/manage/kitchen/`)

Shows today's board by default; use the **← Prev day / Next day →** links at the top to look at another day, or **Print** to print the current view (the page hides buttons/nav when printing so you get a clean prep sheet).

Orders land on this board the moment they're confirmed — either an EFT payment gets verified, or a cash order gets accepted — and leave it once marked ready (to the Collection board).

### What you see

- **Two meters** at the top: orders secured today (against the day's order cap) and cash orders today (against the cash cap).
- **Summary** — every dish/option combination across all orders on the board today, with the total quantity needed and which order numbers contribute to it (e.g. "Chicken Masala Roti Roll — Medium ×8"). This is your cook list.
- **Lock prep list** button, next to the Summary heading — stamps the current time as the kitchen's "prep locked" time. This cannot be undone once clicked (there's no unlock). After locking, anything confirmed later shows up separately in the **Added after lock** section below, so the kitchen knows what wasn't in the original count.
- **Exceptions** — any order carrying a customer note, a kitchen note on one of its dishes, or an allergen flag, listed with the actual note/allergen text so you don't have to open each order.
- **Added after lock** — only appears once you've locked the prep list; lists orders confirmed after that point.
- **Today's run** — one row per order: slot time, order number, customer, item summary, EFT/CASH tag, status, and an action button.

### Actions

| Button | Appears when | What it does | Order moves to |
|---|---|---|---|
| **Start kitchen** | Status is Confirmed (prep) or Cash due | Marks cooking as started | `In kitchen` — customer sees "Cooking" |
| **Mark ready** | Status is In kitchen | Food is packaged and ready | `Ready` — customer sees "Ready to collect", order appears on the Collection board |

There are also two bulk buttons above the run list — **Start kitchen (all confirmed)** and **Mark ready (all in kitchen)** — each with a confirmation pop-up before it fires, for when a whole batch is going into or coming out of the kitchen together.

This page doesn't auto-refresh — if another staff member has actioned an order, reload the page to see the current state. If your click fails (the order already changed), the row shows a "reload the page" error rather than silently failing.

---

## Screen 4 — Collection board (`/manage/collection/`)

Shows all orders that are ready (or about to be), grouped by collection time slot in time order; the slot matching the current time is highlighted with a **Now** tag and shown in the accent colour. Use **← Prev day / Next day →** to look at other days.

### Ticket appearance

Each order is a card showing the order number, customer name, item count, and a tag: **CASH R##.##** for cash orders (so you know the amount to collect) or **PAID** for EFT orders (already settled — nothing to collect). A card for an order still `In kitchen` (not ready yet) is shown faded/greyed with a "Not ready" tag, so you can see what's coming without confusing it for a ready order.

### Actions per ticket

| Button | Appears when | What it does | Order moves to |
|---|---|---|---|
| **Mark ready** | Status is In kitchen | Lets you fast-track a card straight from here if it wasn't already marked ready on the Kitchen desk | `Ready` |
| **Collected** | Status is Ready | Customer has arrived and picked up their food | `Collected` (done) |
| **Uncollect** | Status is Collected | Undo an accidental "Collected" tap — asks for a reason first | Back to `Ready` |

**Uncollect only works within 10 minutes of the original "Collected" click.** After that the button won't work — if a genuine mistake needs correcting after 10 minutes, tell the developer/owner rather than trying to force it.

### Uncollected bucket

Once the collection window plus a grace period (15 minutes by default) has passed, any order still `Ready` moves out of its slot group into a separate **Uncollected** section at the bottom, each with a **No-show** button (with a confirmation pop-up — "This cannot be undone"). No-show cancels the order for that reason; the food/units stay counted as used.

### Close out day

Once the same deadline has passed, a **Close out day** box appears below everything else. It tells you how many remaining ready orders will be marked as no-shows if you proceed, and its button asks you to confirm the exact count before doing it. This is the same action a nightly automatic job runs at 23:30 SAST anyway (as a safety net) — using the button here just does it early and on demand. It cannot be undone.

---

## Screen 5 — Payments — EFT queue (`/manage/payments/`)

Shows every order waiting on an EFT (bank transfer) payment, oldest-lapsing-hold first, then by slot time. Cash orders never appear here — those are on the Cash screen.

| Status shown | Meaning |
|---|---|
| **Awaiting EFT** | Order placed, payment hold timer running, customer hasn't uploaded proof yet |
| **Payment review** | Customer has uploaded proof of payment — needs a staff member to check it |

Each row also shows the amount, the collection slot, a live-updating hold countdown (or **"Lapsed — hold expired"** in red once it runs out), and whether proof has been uploaded (**Uploaded** or **—**).

### Actions per order

| Button | Shown when | What it does | Order moves to |
|---|---|---|---|
| **Verify** | Status is Payment review | Proof looks correct — accept the payment | `Confirmed (prep)` → appears on Kitchen desk |
| **Verify (seen in bank app)** | Status is Awaiting EFT | You can see the payment landed in the bank account even though the customer hasn't uploaded a screenshot yet — asks for a reason first | `Confirmed (prep)` |
| **Reject** | Status is Payment review | Proof is wrong/invalid — asks for a reason first | Back to `Awaiting EFT` (the hold isn't extended automatically — use Extend hold too if the customer needs more time to try again) |
| **Expire now** | Status is Awaiting EFT | Manually close the hold early (e.g. customer says they're not paying) | `Payment expired` (a dead end — the order can be reinstated from the Inbox's "Recently expired" section within 48 hours) |
| **Extend hold** | Always | Gives the customer more time — adds the default EFT hold window (usually 2 hours) to the deadline | Stays in Awaiting EFT, deadline pushed out |

**Note:** clicking Verify updates the customer's own tracker on their phone from "Payment" straight to "Confirmed" immediately.

**Hold extensions are limited.** By default an order's hold can only be extended once — clicking Extend hold again past that limit fails with a message saying the maximum extensions have been used.

This page doesn't auto-refresh either — reload to see other staff members' changes.

---

## Screen 6 — Cash (requests) (`/manage/cash/`)

Every order where the customer chose to pay cash on collection, oldest first — this is a same-day queue, so there's no date picker, just today's outstanding requests. This is the exact same list as the Inbox's "Cash requests" section, just without everything else around it.

### Actions

| Button | What it does | Order moves to |
|---|---|---|
| **Accept** | Confirms the order — moves it to the kitchen board as cash-due, ready to prep | `Cash due` → appears on Kitchen desk (still needs cash collected on pickup) |
| **Reject** | Declines the request — cancels the order and frees its slot capacity. Confirmation pop-up first: "Reject this cash order? It will be cancelled and the slot freed." | `Cancelled` |

---

## Screen 7 — Daily controls (`/manage/days/`, or a specific day at `/manage/days/<date>/`)

Visiting `/manage/days/` with no date takes you straight to today's page. This screen is your day-by-day override layer — it lets you sell out one dish, close one slot, or close the whole day, without touching the monthly menu (that's the Menu editor, below).

### What you can change

**Day section:**
- **Open** checkbox — whether the day is taking orders at all.
- **Daily order cap** — override just for this day.
- **Same-day cut-off** — the time same-day ordering closes.
- **Window start / Window end** — the collection window for the day.
- **Internal notes** — a free-text field, staff-only, not shown to customers.

**Slots table** — one row per collection slot with its time window, a capacity number you can edit (it can never be set below the slot's current occupancy — you'll get a validation error listing the minimum), a **Closed** checkbox, and a read-only "Occupying" count.

**Dishes today table** — one row per active dish, with an **Available** checkbox for that specific day and a **Max units** number (leave blank for uncapped), plus a read-only "Used today" count.

### Saving

Click **Save daily controls** at the bottom. If any of your changes would affect orders that already exist — closing a slot or the whole day while it still has active (occupying) orders on it — the page won't save immediately. Instead you'll see a warning box listing every affected order by number, customer and status, and:

- For each slot you're closing that has orders on it, a **Move all to…** dropdown plus a **Move all** button to shift every one of that slot's orders to a different open slot in one click.
- A checkbox: *"I understand this affects the orders listed above and want to save anyway."* — tick this (after moving orders, or deliberately leaving them where they are) and click Save again to go through.

Existing orders on a slot or day you close **keep their booking** — closing only stops *new* orders being placed against it.

---

## Screen 8 — Menu editor (`/manage/menu/`)

Lists every dish, including archived ones, in the same order they appear on the public menu (category, then sort order, then name) — archived dishes are shown dimmed at the end of their category. Each row shows category, sort order, name (a link to edit it), price, whether it's active on the public menu, a **Live**/**Archived** badge, and how many currently-active orders reference that dish.

- **+ New dish** (top right) opens a blank dish form.
- Click a dish's name, or **Edit**, to open its edit form (`/manage/menu/<id>/`).

### The dish form

Fields: Slug (create only — permanent once set, cannot be changed afterwards), Name, Price (cents), Portion label, Short description, Long description, Spice default, Allergen text, Dietary tags, Category, Sort order, "Is active on menu" checkbox, "Allow notes" checkbox. Click **Create dish** or **Save dish**.

**Image upload** (edit screen only) — a separate small form below the main one: choose a JPEG/PNG/WebP file and click **Upload image**.

**Options & values** (edit screen only) — for things like spice level, size, or extras:
- Add an option with a name, a **Required** checkbox, and a sort number, via the **Add option** form at the bottom.
- Under each option, add values (name, price delta in cents, sort order) via its own **Add value** form; each value has a **Yes/No — mark (un)available** toggle and a **Delete** button (with a confirmation pop-up — deleting is permanent).
- **Delete option** removes the option and all its values — also asks for confirmation first.

**Archiving a dish** — a boxed section at the bottom, **Archive dish**. If the dish has no orders currently using it, one click archives it (also confirmed via a pop-up) and it disappears from the public menu immediately. If it does have active orders referencing it, you'll see the exact count and must tick a confirmation checkbox before the **Archive dish** button will go through — this is safe to do even then, because every existing order line keeps its own frozen copy of the dish's name and price regardless of what happens to the Dish record afterwards. Archiving is a soft delete: an **Unarchive** button on the dish's edit page brings it back.

---

## Screen 9 — New assisted order (`/manage/orders/new/`)

**This is for staff placing an order on the customer's behalf** — a phone-in order, a walk-in customer who wants a human to take their order, or someone ordering via a WhatsApp conversation with you rather than the website. It is never used for the customer's own self-service web checkout (those always come through as "Website" orders automatically).

It uses exactly the same underlying reservation logic as the customer's own online checkout — same capacity checks, same dish-availability rules, same order numbering — so anything you place here counts against the day/slot/cash/dish caps exactly like a normal web order would.

### Before you start, get from the customer:

- Their full name.
- Their mobile number (must be a valid South African mobile number — the system will reject anything else).
- What they want to order (dish, quantity, and any required options like spice level or size).
- Which collection slot they want.
- How they're paying — EFT or cash (cash only shows as an option if it's currently enabled in Settings).
- If it's a same-day order placed after the normal online cut-off time, you'll also need a short reason to enter (see "After-cut-off reason" below) — and this only works at all if the owner has turned that feature on.

### Walking through the form, field by field

**Date bar at top** — shows the collection date you're placing this order for, with **← Prev day / Next day →** links to change it (limited to today through the pre-order horizon, typically the next 7 days).

**Customer section:**
- **Full name** — free text, 2–80 characters.
- **Mobile number** — must resolve to a valid SA mobile number.
- **Order source** — radio buttons: Phone, In person, or WhatsApp (assisted). Pick whichever matches how the customer actually reached you.
- **Order note** (optional) — up to 200 characters, visible to the kitchen.

**Collection section:**
- **Slot** — a dropdown of the day's collection slots, each showing its current occupancy (e.g. "12:00–12:30 (4/10)"); any slot that's full or closed is shown disabled and can't be selected.
- **After-cut-off reason** — only shown when you're placing an order for *today*. If the owner has enabled after-cut-off assisted orders in Settings, this becomes a required text field for a same-day order placed after the normal cut-off time. If that setting is off, the field is shown but disabled, with a note explaining that a same-day order will be refused until an admin turns it on.

**Payment section:**
- **Method** — EFT, or Cash if cash is currently enabled.
- **EFT status** (only relevant if Method is EFT) — three options:
  - **Awaiting EFT (default)** — the normal case: the order is created exactly like a web order, with a payment hold running, and will show up on the Payments queue for someone to verify once the customer pays.
  - **Customer says paid** — use this if the customer tells you (e.g. over the phone) that they've already paid but you don't have proof yet. This moves the order straight into "Payment review" so it's in the same review queue a real proof upload would land it in.
  - **Staff saw the funds** — use this only if you have personally already seen the money land in the bank account. This confirms the payment immediately (no waiting) and sends the order straight to the kitchen board. **A reason is mandatory for this option** — a text box appears; you must fill it in or the order can't be escalated this way (it can still be created as a plain hold instead).
- **Reason** — the text box backing "Staff saw the funds" above.

**Dishes section:** every active dish for the selected day, each with a quantity box (0–20) and, where the dish has options (like spice level or extras), the option choices inline underneath the dish name — required options are radio buttons (pick one), optional ones are checkboxes (pick any). A dish that's sold out for the day is shown greyed out with "— sold out today" and its quantity box disabled.

Click **Create order** at the bottom. On success you're taken back to the Inbox with a confirmation message naming the new order number. If the escalation to "Payment review" or "Staff saw the funds" fails for some reason (e.g. the reason was somehow missing), the order is still created as a plain hold — you'll get a warning message rather than losing the order entirely.

**If something's wrong with the form** — a missing name, an invalid mobile number, no dishes selected, no slot chosen, capacity has run out since you loaded the page — you'll see a list of specific error messages at the top and nothing is created; fix the fields called out and click Create order again.

---

## Other screens you may come across

| Screen | URL | Who can use it | What it's for |
|---|---|---|---|
| **Settings** | `/manage/settings/` | Owner and Admin only | Order/cash caps, EFT hold duration, extension limits, collection grace period, bank details, and around 40 other site-wide settings — every field on this form directly maps to a setting. Every save is written to a settings audit log automatically. There's no separate nav link for Admin roles even though Admins can open it (see Troubleshooting below) — Admins can still reach it by typing the URL. |
| **Team** | `/manage/team/` | Admin only (not Owner) | Invite staff by email (choose their role: admin/owner/manager), remove someone from the allow-list, or change someone's role. **There is no link to this page anywhere in the staff menu** — you have to know the URL. If you're an Owner and need to manage the team, ask an Admin, or navigate here directly and you'll be redirected away with "Team management requires admin access." |
| **Change password** | `/manage/change-password/` | Any logged-in staff | Voluntary password change, or the forced screen you land on with a temporary password. |

---

## Roles — who can do what

There are three staff roles (`UserRole` in the system): **Admin**, **Owner**, and **Manager**. In practice:

- **Manager** — everyday access to every board: Inbox, Calendar, Kitchen desk, Collection, Payments, Cash, Daily controls, Menu editor, New assisted order.
- **Owner** — everything a Manager can do, **plus** Settings, plus one extra permission most managers won't hit: **only an Owner or Admin can cancel an order once it's already `In kitchen` or `Ready`.** A Manager trying this gets an "Only the owner can cancel from this stage" error.
- **Admin** — everything an Owner can do, plus Team management (`/manage/team/`) to invite/remove staff and change roles.

If you try an action your role doesn't allow, you won't be shown a broken page — the system either hides the button/link entirely, or (for Settings/Team specifically) shows a plain "access only"/"requires admin access" message and sends you back to the Inbox.

---

## Complete order flow (EFT)

```
Customer places order (or staff places an assisted order)
        ↓
  [Awaiting EFT]         ← Payments screen — hold timer running
        ↓ (customer uploads proof, or staff marks "Customer says paid")
  [Payment review]       ← Payments screen — staff clicks VERIFY
        ↓
  [Confirmed (prep)]     ← Kitchen desk — staff clicks START KITCHEN
        ↓
   [In kitchen]          ← Kitchen desk / Collection board — staff clicks MARK READY
        ↓
     [Ready]             ← Collection board — customer arrives, staff clicks COLLECTED
        ↓
   [Collected] ✓
```

A hold that runs out with no action becomes **[Payment expired]** — a dead end unless reinstated from the Inbox within 48 hours (a fresh hold is created).

## Complete order flow (cash)

```
Customer places a cash order (or staff places an assisted cash order)
        ↓
  [Cash request]         ← Cash screen — staff clicks ACCEPT
        ↓
   [Cash due]            ← Kitchen desk — staff clicks START KITCHEN
        ↓
   [In kitchen]          ← Kitchen desk / Collection board — staff clicks MARK READY
        ↓
     [Ready]             ← Collection board — customer pays cash + staff clicks COLLECTED
        ↓
   [Collected] ✓
```

Rejecting a cash request, or an order left `Ready` past the collection deadline with no-show/close-out applied, both end in **[Cancelled]**.

---

## Quick reference — what the customer sees at each step

| Order status (internal) | Customer tracker shows |
|---|---|
| Awaiting EFT | "Payment" step — upload your proof of payment |
| Payment review | "Payment" step — proof is with us, confirming shortly |
| Cash request | Waiting for staff to accept the cash order |
| Confirmed (prep) / Cash due | "Confirmed" step |
| In kitchen | "Cooking" step |
| Ready | "Ready to collect" step |
| Collected | Terminal — order complete |
| Payment expired / Cancelled | Terminal — order ended |

---

## Troubleshooting / FAQ

**A button did nothing, or a row shows a red error saying to reload the page.**
Someone else (or a background job) already changed that order's status since your screen loaded — the system refuses to apply an action against a status it no longer matches, to stop two staff members' clicks from clashing. Reload the page and check the order's current status before trying again.

**I tried to cancel an order that's already In kitchen or Ready and got an error.**
That's expected if you're a Manager — only an Owner or Admin can cancel an order at that late a stage. Ask an Owner/Admin to do it, or hold the order at that status and contact the customer directly.

**A "reason" box suddenly appeared and won't let me submit without text.**
A handful of actions are deliberately gated behind a mandatory reason, because they bypass a normal safety check: verifying EFT payment without proof ("seen in bank app"), rejecting a payment, reinstating an expired order, uncollecting an order, and confirming "Staff saw the funds" on an assisted order. Just type a short, honest reason (e.g. "Customer showed me the bank SMS") — it's recorded against the order for the audit trail, it isn't shown to the customer.

**I marked an order Collected by mistake.**
Use **Uncollect** on the Collection board — but only within **10 minutes** of the original click. After that the button stops working; ask the developer/owner if a correction is genuinely needed past that window.

**An EFT hold ran out before the customer paid.**
The order moves to **Payment expired** automatically and drops off the Payments queue. It still shows up in the Inbox's "Recently expired" section for 48 hours, where you can **Reinstate** it (with a reason) — that opens a brand-new hold, but only if the day/slot/dish still has room. After 48 hours it's easiest to just have the customer place a new order.

**I can't extend a hold any further.**
Holds can only be extended a limited number of times (one, by default) — Extend hold will refuse once that limit is hit. Use Verify (seen in bank app) if you can confirm the payment another way, or let it lapse and reinstate later if the customer still wants to order.

**A slot or dish won't let me set its capacity/limit below a certain number.**
Daily controls won't let a slot's capacity go below how many orders are already occupying it — you'll see the exact minimum in a validation message. Move some of those orders to another slot first (the "Move all to…" tool in the confirmation banner) if you need to shrink it further.

**I'm a Manager and can't see a Settings link.**
Correct — Settings is Owner/Admin only, and the link is hidden from Managers entirely (not just blocked). If you're an Admin and don't see the Settings link either, that's a real inconsistency in the current build, not something you're doing wrong — see the note below.

**I need to add or remove a staff member, or change someone's role.**
That's the Team screen at `/manage/team/` — Admin role only (an Owner cannot do this, even though Owner outranks Manager everywhere else). There's currently no link to it in the staff menu, so you need the URL directly.

**A dish I need to sell out today isn't in Daily controls.**
Daily controls only lists dishes that are active on the public menu (`Is active on menu` checked in the Menu editor). Check the Menu editor first if a dish seems to be missing.

---

## Known inconsistencies in the current build (not your fault — flagged for the developer)

- The Staff dropdown only shows the **Settings** link when your role is exactly `owner`; Admins (who are also allowed to open Settings via `owner_required`) don't get a nav link to it and must type the URL.
- There is **no nav link anywhere** to the **Team** screen (`/manage/team/`), even for Admins who are the only role allowed to use it.
- The EFT queue's "Extend hold" button text says it "usually" adds 2 hours, but the actual amount added is whatever the owner has set in Settings (`hold_extension_minutes`, default 15 minutes) — the button's own hover text and the real default don't currently match.
