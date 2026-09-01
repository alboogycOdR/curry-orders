# Roti Connect — Staff Order Management Guide

This guide explains every screen a kitchen staff member uses, in the order they are used during a normal service day.

---

## Getting in

**Login page:** `http://204.168.249.99:8102/manage/login/`

Enter your username and password. After logging in you land on the Inbox. You can also reach the login page from the **More** tab → **Kitchen staff login** on any mobile browser.

---

## Screen 1 — Inbox (`/manage/`)

The landing page after login. Shows urgent items at a glance:

- Orders whose EFT hold has lapsed but no proof has arrived yet
- Orders with special notes or allergen flags
- Recently expired or cancelled orders

Use this as your morning briefing. If something needs immediate action it will be here.

---

## Screen 2 — EFT Payments Queue (`/manage/payments/`)

Shows every order waiting on payment, in two states:

| State | Meaning |
|---|---|
| **Awaiting EFT** | Order placed, hold timer running, no proof yet |
| **Payment review** | Customer has uploaded proof — needs staff verification |

### Actions per order

| Button | What it does | Order moves to |
|---|---|---|
| **Verify** | Proof is valid — accept the payment | `Confirmed` → appears on Kitchen board |
| **Reject** | Proof is wrong or missing — cancel the order | `Cancelled` |
| **Extend hold** | Give the customer more time to pay | Stays in Awaiting EFT |
| **Expire now** | Manually close the hold early | `Expired` (terminal) |

> **Note:** Once you click Verify, the customer's tracker on their phone immediately updates from "Payment" to "Confirmed."

---

## Screen 3 — Kitchen Board (`/manage/kitchen/`)

Appears after an EFT order is verified or a cash order is accepted. Default view is today; use the date arrows to view another day.

### What you see

- **Prep summary** — total quantities across all orders (e.g. "8× Chicken Masala Roti Roll — Medium"). Use this to know exactly what to cook.
- **Exceptions band** — any order with a kitchen note, allergen flag, or special instruction.
- **Added after lock** — orders confirmed after the prep list was locked (late additions).
- **Order tickets** — one card per order, with its items and slot time.

### Actions per ticket

| Button | What it does | Order moves to |
|---|---|---|
| **Start** | Kitchen has begun cooking this order | `In kitchen` → customer sees "Cooking" |
| **Mark ready** | Food is packaged and waiting | `Ready` → customer sees "Ready to collect" |

---

## Screen 4 — Collection Board (`/manage/collection/`)

Shows all `Ready` orders, grouped by collection time slot. The current slot is highlighted.

When a customer arrives and collects their order:

| Button | What it does |
|---|---|
| **Collected** | Order complete — moves to `Collected` (done) |

Orders that are still `Ready` after the collection window closes move to an **Uncollected** bucket at the bottom.

---

## Supporting screens

| Screen | URL | When to use |
|---|---|---|
| **Cash requests** | `/manage/cash/` | Approve or reject customers requesting cash-on-collection payment |
| **Daily controls** | `/manage/days/` | Open/close individual slots; lock the prep list; close out the day |
| **Calendar** | `/manage/calendar/` | 8-day view of how full each day's slots are |
| **Menu editor** | `/manage/menu/` | Add, edit, or archive dishes; upload photos; change prices |
| **Settings** | `/manage/settings/` | Order cap, cash cap, EFT hold duration, bank details |

---

## Complete order flow (EFT)

```
Customer places order
        ↓
  [Awaiting EFT]         ← EFT Payments Queue — hold timer running
        ↓ (customer uploads proof)
  [Payment review]       ← EFT Payments Queue — staff clicks VERIFY
        ↓
  [Confirmed / prep]     ← Kitchen Board — staff clicks START
        ↓
   [In kitchen]          ← Kitchen Board — staff clicks MARK READY
        ↓
     [Ready]             ← Collection Board — customer arrives, staff clicks COLLECTED
        ↓
   [Collected] ✓
```

## Complete order flow (cash)

```
Customer places order
        ↓
  [Cash request]         ← Cash Requests screen — staff clicks ACCEPT
        ↓
  [Confirmed / prep]     ← Kitchen Board — staff clicks START
        ↓
   [In kitchen]          ← Kitchen Board — staff clicks MARK READY
        ↓
     [Ready]             ← Collection Board — customer pays cash + staff clicks COLLECTED
        ↓
  [Collected cash] ✓
```

---

## Quick reference — what the customer sees at each step

| Order status (internal) | Customer tracker shows |
|---|---|
| Awaiting EFT | Payment (step 2) — "Upload your proof of payment" |
| Payment review | Payment (step 2) — "Your proof is with us, confirming shortly" |
| Confirmed / prep | Confirmed (step 3) |
| In kitchen | Cooking (step 4) |
| Ready | Ready to collect (step 5) |
| Collected | Terminal — "Collected, enjoy your meal" |
| Cancelled / expired | Terminal — order ended |

