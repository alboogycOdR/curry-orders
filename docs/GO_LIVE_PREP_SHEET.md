# Go-Live Prep Sheet — Brandon's Kitchen Order System

**Docket No. 001** · Issued 29 Aug 2026 · Owner: Brandon

All the **code** for taking orders, holding slots, chasing EFT payments and running the kitchen board is built (see `docs/DECISIONS.md` and §22 of `docs/SPEC_v1.1.md` for what's shipped). What's left to open the doors is **information only the owner can supply** — the menu, the bank account, the address, a few policy decisions.

Fourteen items below, grouped into 7 stations, mirroring the owner-input table in `docs/SPEC_v1.1.md` §23. Nothing on this list needs a developer — it needs the owner.

- 🔴 **Blocking** — pilot cannot start without this
- 🟢 **Confirm** — a sensible default is proposed; just say yes or change it

A matching print-ready copy is at `docs/GO_LIVE_PREP_SHEET.pdf`.

---

## 01 · Menu & Pricing
*Feeds the menu editor (build in progress)*

### 🔴 Final dish list — Blocking
Name, price, portion size, any options (e.g. spice level, sides), allergen text and dietary tags — one row per dish. A spreadsheet is fine.

> _Answer:_

### 🔴 Dish option groups (Spice / extras) — Blocking
Each item that needs a heat level (Mild / Medium / Hot) must have a **Spice** option group added in the staff menu editor (`/manage/menu/`). Items that include chips (masala roti rolls, gatsbys) should also have **Extra roti** (+R12) and **Chips** (−R5) optional groups added. Dev seed (`manage.py seed_dev`) sets these up automatically for local testing — production dishes must be configured manually before launch.

> _Answer (note when done):_

### 🔴 Dish photos — Blocking
One photo per dish, landscape orientation preferred. Phone photos are fine — they'll be resized for the menu and dish pages.

> _Answer:_

---

## 02 · Money
*EFT page, checkout, receipt wording*

### 🔴 Bank details — Blocking
Bank, account name, account number, branch code, account type — shown on the EFT payment page, exactly as customers must enter them.

> _Answer:_

### 🟢 VAT registration status — Confirm
Registered or not, and VAT number if registered — affects receipt wording.
→ *Default assumed:* `not VAT registered`

> _Answer:_

### 🟢 Cash ordering window — Confirm
Keep cash orders same-day only (00:00–10:00), or also allow cash for tomorrow's collection?
→ *Recommended:* `keep same-day only` for the pilot, revisit with real no-show data.

> _Answer:_

### 🟢 No-show refund policy — Confirm
If a customer pays by EFT, is verified, then never collects — do they get a refund by default, or only if the owner decides to make an exception?
→ *Default assumed:* `no automatic refund`, owner exception only.

> _Answer:_

---

## 03 · Collection
*Confirmed order page, collection ticket*

### 🔴 Address & arrival instructions — Blocking
Full collection address, plus anything a stranger needs to know arriving at a home: which gate, where to park, no hooting, what to say at the door.

> _Answer:_

---

## 04 · Policies & Compliance
*/policies page, dish pages*

### 🔴 Allergen / home-kitchen disclaimer — Blocking
Owner's own wording on allergens and operating from a home kitchen. The site currently shows a placeholder "not yet provided" — this replaces it.

> _Answer:_

### 🔴 EU data-hosting sign-off — Blocking
Order and payment-proof data is stored on a server in Finland (POPIA §72 permits this — the EU's protection standard qualifies). Needs the owner's written confirmation that this is acceptable, as the information officer.

> _Answer:_ ☐ Approved ☐ Not yet

---

## 05 · Brand & Contact
*Header, help page, EFT page, theme*

### 🔴 Support WhatsApp number — Blocking
Shown on the header, help page and EFT page for payment problems only — not for routine orders.

> _Answer:_

### 🔴 Logo & brand colours — Blocking
The site currently runs a placeholder theme. Send a logo file and preferred colours, or say "keep the placeholder" for the pilot.

> _Answer:_

---

## 06 · Team
*Staff accounts, seeded at launch*

### 🔴 Owner + two managers — Blocking
Full name and email for each of the three staff accounts. Each gets a temporary password and must set their own on first login.

> _Answer:_

---

## 07 · Hosting & Domain
*Deploy configuration, backups*

### 🔴 Off-server backup destination — Blocking
Where nightly database and photo backups get copied to — needs to live outside the server itself. A Hetzner Storage Box is the natural fit (same provider, separate failure domain) — needs an account and access credentials.

> _Answer:_

### 🔴 Site & photo hostnames — Blocking
Two subdomains under `rwc.org.za` — one for the ordering site, one for photo delivery, e.g. `orders.` and `media.`.

> _Answer:_

---

## Sign-off

Once every item above is filled in, the pilot go-live checklist (`docs/SPEC_v1.1.md` §21) can run: backup/restore drill, bank details verified with a R 1 test order, both managers walked through their first order, then a two-week pilot with a review date.

| Owner signature — date | Returned to developer — date |
|---|---|
| | |
