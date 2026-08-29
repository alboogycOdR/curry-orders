# Dish list — draft transcription (§23 owner input)

Transcribed from a handwritten menu sheet (photo dated 2026-08-28) plus the
owner's own text description. This is a **draft**, not the final §23 dish
list: no prices, portions in Rand, allergen text, dietary tags or photos
were on the sheet, and a few marks are ambiguous — flagged below rather
than guessed. Confirm against this before it becomes seed data for
`manage.py seed_pilot`.

## As read

**A — Roti & Curry** (Portion 1)
- Chicken
- Steak

**A3 — Masala Roti Roll** (Portion 1)
- Chips, steak, roti — steak
- " " — chicken
- (i.e. two variants: steak roll, chicken roll; "steak" is written then
  crossed out once at the top of this block — read as the section title
  being corrected to "Roti Roll", not as removing steak from the fillings)

**B — Roti & Gatsby (Large)**
- B1: Chicken masala → Portion 4
- B2: Masala steak → Portion 4

**C — Gatsby**
- Chicken masala → Portion 4
- Steak masala → Portion 4
- "Full house" masala steak (egg, cheese)

**D — Italian Lasagne** (Portion 1)
- Beef

## Resolved

- **"Port N" = portion, feeds N people** (confirmed by the owner,
  2026-08-29). So: Roti & Curry, the Roti Roll variants, and the Lasagne
  are all Portion 1 (serves 1); both Roti & Gatsby (Large) items and the
  Chicken/Steak Masala Gatsby are Portion 4 (serves 4). The Full House
  Masala Steak Gatsby had no portion marked on the sheet — still open,
  see below.

## Ambiguous — do not build against these without confirming

1. **Corner annotations** — "AMUKAI"/"AMWARE"(?), `WOB`, `APP`, "basket 2",
   "correspond", "Promo", "RCA1/H", "counter pre-orders", "UBER EATS
   delivery" — these look like notes from an existing ordering platform or
   till system, not menu structure. Left out of the transcription above;
   flag if any of them need to carry into this system (e.g. an "Uber Eats"
   channel is explicitly out of scope per spec §2.2).
2. Whether Category A ("Roti & Curry") and A3 ("Masala Roti Roll") are two
   separate dishes or two options on one dish — modelled above as separate
   dishes since they have different fillings/structure, but worth
   confirming against `dishes` (§7.3) vs `dish_options` (§7.4).
3. Full House Masala Steak Gatsby's portion size — not marked on the
   original sheet, unlike every other item.

## Still outstanding for §23 regardless of the above

Prices, portion sizes/weights, allergen text, dietary tags, and dish
photos — none of these were on the sheet.
