// cart.js — the customer cart, held in the browser only.
//
// PR 4 (rc_cart_v2): cart is now a structured object with a `lines`
// array rather than a dish-id-keyed map. This allows lines that carry
// heat/extras/notes alongside qty, and lets checkout.js send
// `kitchen_note` per line to POST /api/checkout (KD-5).
//
// Storage key is `rc_cart_v2`; `bk_cart_v1` / `bk_day_v1` / bk_slot*
// / bk_pay_v1 are read-only migration sources — never written again.
// `bk_day_v1` stored an integer day-index; that is NOT migrated to
// `dayIso` (an ISO date string) — `dayIso` stays null until the user
// picks a chip.  Old keys are cleared on `clearCart()`.
//
// Loaded on every page (base.html, `defer`), before any per-page
// script — order.js/checkout.js/basket.js/item-sheet.js all assume
// `window.BKCart` exists.
//
// Removed from the public API in this PR (PR 4):
//   getCart / setCart / setLine / bump / getDay / setDay
// All callers (order.js, checkout.js, dish.js, reorder.html) are
// ported in the same commit.
(function () {
  "use strict";

  var V2_KEY      = "rc_cart_v2";
  var V1_CART_KEY = "bk_cart_v1";
  var V1_DAY_KEY  = "bk_day_v1";   // integer index — NOT mapped to dayIso
  var V1_SLOT_KEY = "bk_slot_v1";
  var V1_SLOT_ID_KEY = "bk_slot_id_v1";
  var V1_PAY_KEY  = "bk_pay_v1";

  // ---------------------------------------------------------------- storage helpers

  function readJSON(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }
  function writeJSON(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) { /* storage unavailable — state won't persist */ }
  }
  function removeKey(key) {
    try { localStorage.removeItem(key); } catch (e) { /* ignore */ }
  }
  function readStr(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }

  // ---------------------------------------------------------------- format helper (mirrors core.money exactly)

  function rands(cents) {
    var n = Math.round(Number(cents));
    var sign = n < 0 ? "-" : "";
    var abs = Math.abs(n);
    var wholeRand = Math.floor(abs / 100);
    var subCents = abs % 100;
    var grouped = String(wholeRand).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return sign + "R " + grouped + "." + (subCents < 10 ? "0" : "") + subCents;
  }

  // ---------------------------------------------------------------- v1 → v2 migration (once)
  // Converts the old `{ [compositeId]: {name, price, qty} }` map into
  // v2 lines.  `compositeId` is either a bare dish pk (string) or
  // "dishId:optId1,optId2".  heat/extras/notes/photoUrl are left empty
  // — they are not recoverable from the v1 blob.

  function _parseV1Key(key) {
    var parts = String(key).split(":");
    var itemId = parseInt(parts[0], 10);
    var optionValueIds = parts[1]
      ? parts[1].split(",").map(function (s) { return parseInt(s, 10); })
      : [];
    return { itemId: itemId, optionValueIds: optionValueIds };
  }

  function _migrateV1() {
    var v1 = readJSON(V1_CART_KEY, null);
    if (!v1 || typeof v1 !== "object" || Array.isArray(v1)) return null;
    var lines = [];
    Object.keys(v1).forEach(function (id) {
      var entry = v1[id];
      if (!entry || typeof entry.qty !== "number" || entry.qty <= 0) return;
      var parsed = _parseV1Key(id);
      var unitPrice = typeof entry.price === "number" ? entry.price : 0;
      lines.push({
        id: id,                          // reuse old key as stable id
        itemId: parsed.itemId,
        name: String(entry.name || ""),
        heat: "",
        extras: [],
        notes: "",
        qty: entry.qty,
        unitPrice: unitPrice,
        lineTotal: unitPrice * entry.qty,
        photoUrl: "",
        optionValueIds: parsed.optionValueIds,
      });
    });
    var slotId = readStr(V1_SLOT_ID_KEY);
    var slotLabel = readStr(V1_SLOT_KEY);
    var pay = readStr(V1_PAY_KEY) || "eft";
    return {
      version: 2,
      lines: lines,
      dayIso: null,      // V1_DAY_KEY was an integer index — not portable
      slotLabel: slotLabel,
      slotId: slotId !== null ? parseInt(slotId, 10) : null,
      pay: pay,
    };
  }

  // ---------------------------------------------------------------- state

  var _state = null; // lazy init on first getState()

  function _empty() {
    return { version: 2, lines: [], dayIso: null, slotLabel: null, slotId: null, pay: "eft" };
  }

  // Validate and coerce values read from storage so corrupt/stale data
  // can never propagate into the cart logic.
  function _validateState(s) {
    // lines must be an array
    if (!Array.isArray(s.lines)) s.lines = [];
    // dayIso must be a YYYY-MM-DD string or null
    if (s.dayIso !== null && s.dayIso !== undefined) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(String(s.dayIso))) s.dayIso = null;
    }
    // slotId must be a positive integer or null
    if (s.slotId !== null && s.slotId !== undefined) {
      var sid = parseInt(String(s.slotId), 10);
      if (isNaN(sid) || sid <= 0) s.slotId = null;
      else s.slotId = sid;
    }
    return s;
  }

  function getState() {
    if (_state) return _state;
    var stored = readJSON(V2_KEY, null);
    if (stored && stored.version === 2) {
      _state = _validateState(stored);
    } else {
      // Attempt v1 migration; fall back to empty
      _state = _validateState(_migrateV1() || _empty());
      writeJSON(V2_KEY, _state);
    }
    return _state;
  }

  function setState(partial) {
    var s = getState();
    Object.keys(partial).forEach(function (k) { s[k] = partial[k]; });
    writeJSON(V2_KEY, s);
    refreshHeader();
  }

  // ---------------------------------------------------------------- lines API

  function getLines() {
    return getState().lines;
  }

  // Stable line id: "itemId:sortedOptIds" or "itemId" when no opts.
  function _lineId(itemId, optionValueIds, notes) {
    var sorted = (optionValueIds || []).slice().sort(function (a, b) { return a - b; });
    var base = sorted.length ? String(itemId) + ":" + sorted.join(",") : String(itemId);
    // notes are NOT part of the id; two lines with different notes but
    // same item+options merge (last notes wins on upsert).
    return base;
  }

  function upsertLine(line) {
    // line: {itemId, name, heat, extras[], notes, qty, unitPrice, lineTotal, photoUrl, optionValueIds[]}
    var lines = getLines();
    var id = _lineId(line.itemId, line.optionValueIds, line.notes);
    var existing = null;
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].id === id) { existing = lines[i]; break; }
    }
    if (existing) {
      existing.qty += (line.qty || 1);
      existing.lineTotal = existing.unitPrice * existing.qty;
      if (line.notes) existing.notes = line.notes;
    } else {
      var newLine = {
        id: id,
        itemId: line.itemId,
        name: line.name || "",
        heat: line.heat || "",
        extras: line.extras || [],
        notes: line.notes || "",
        qty: line.qty || 1,
        unitPrice: line.unitPrice || 0,
        lineTotal: line.lineTotal || (line.unitPrice || 0) * (line.qty || 1),
        photoUrl: line.photoUrl || "",
        optionValueIds: (line.optionValueIds || []).slice().sort(function (a, b) { return a - b; }),
      };
      lines.push(newLine);
    }
    setState({ lines: lines });
  }

  function updateLine(id, patch) {
    // patch may include: qty, heat, extras, notes, unitPrice, optionValueIds
    var lines = getLines();
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].id !== id) continue;
      var line = lines[i];
      if (patch.qty !== undefined) line.qty = patch.qty;
      if (patch.heat !== undefined) line.heat = patch.heat;
      if (patch.extras !== undefined) line.extras = patch.extras;
      if (patch.notes !== undefined) line.notes = patch.notes;
      if (patch.optionValueIds !== undefined) {
        line.optionValueIds = patch.optionValueIds.slice().sort(function (a, b) { return a - b; });
        // recalculate id if options changed
        var newId = _lineId(line.itemId, line.optionValueIds, line.notes);
        line.id = newId;
      }
      if (patch.unitPrice !== undefined) line.unitPrice = patch.unitPrice;
      line.lineTotal = line.unitPrice * line.qty;
      if (line.qty <= 0) {
        lines.splice(i, 1);
      }
      setState({ lines: lines });
      return;
    }
  }

  function removeLine(id) {
    var lines = getLines().filter(function (l) { return l.id !== id; });
    setState({ lines: lines });
  }

  function clearCart() {
    setState({ lines: [], slotLabel: null, slotId: null });
    // Remove legacy keys on a successful checkout so they never re-trigger migration
    removeKey(V1_CART_KEY);
    removeKey(V1_DAY_KEY);
    removeKey(V1_SLOT_KEY);
    removeKey(V1_SLOT_ID_KEY);
    removeKey(V1_PAY_KEY);
  }

  function totals() {
    var count = 0, total = 0;
    getLines().forEach(function (l) {
      count += l.qty;
      total += l.qty * l.unitPrice;
    });
    return { count: count, total: total };
  }

  // ---------------------------------------------------------------- day / slot / pay accessors

  function getDayIso() {
    return getState().dayIso || null;
  }
  function setDayIso(iso) {
    setState({ dayIso: iso || null });
  }
  function getSlot() {
    return getState().slotLabel || null;
  }
  function setSlot(s) {
    setState({ slotLabel: s || null });
  }
  function getSlotId() {
    var v = getState().slotId;
    return (v === null || v === undefined) ? null : parseInt(String(v), 10);
  }
  function setSlotId(id) {
    setState({ slotId: (id === null || id === undefined) ? null : parseInt(String(id), 10) });
  }
  function getPay() {
    return getState().pay || "eft";
  }
  function setPay(p) {
    setState({ pay: p });
  }

  // ---------------------------------------------------------------- header badge / sticky bar

  function refreshHeader() {
    var t = totals();

    var summaryEl = document.getElementById("cart-summary");
    if (summaryEl) {
      if (t.count === 0) {
        summaryEl.hidden = true;
        summaryEl.textContent = "";
      } else {
        summaryEl.hidden = false;
        summaryEl.textContent =
          t.count + (t.count === 1 ? " item · " : " items · ") + rands(t.total);
      }
    }

    var badgeEls = Array.prototype.slice.call(
      document.querySelectorAll("#nav-cart-badge, [data-cart-badge]")
    );
    var checkoutLink = document.getElementById("nav-checkout-link");
    var mobileBasketLink = document.getElementById("mobile-nav-basket-link");
    if (badgeEls.length) {
      if (t.count === 0) {
        badgeEls.forEach(function (b) { b.hidden = true; });
        if (checkoutLink) checkoutLink.setAttribute("aria-label", "Checkout");
        if (mobileBasketLink) mobileBasketLink.setAttribute("aria-label", "Basket");
      } else {
        badgeEls.forEach(function (b) {
          b.hidden = false;
          b.textContent = t.count > 99 ? "99+" : String(t.count);
        });
        if (checkoutLink) {
          checkoutLink.setAttribute(
            "aria-label",
            "Checkout, " + t.count + (t.count === 1 ? " item" : " items")
          );
        }
        if (mobileBasketLink) {
          mobileBasketLink.setAttribute(
            "aria-label",
            "Basket, " + t.count + (t.count === 1 ? " item" : " items")
          );
        }
      }
    }

    var sticky = document.getElementById("sticky-basket-bar");
    if (sticky) {
      if (t.count === 0) {
        sticky.hidden = true;
        sticky.textContent = "View basket";
      } else {
        sticky.hidden = false;
        sticky.textContent =
          t.count + (t.count === 1 ? " item · " : " items · ") + rands(t.total) + " View basket";
      }
    }
  }

  // ---------------------------------------------------------------- cross-tab sync
  // When another tab writes to the same storage key, reset _state so the
  // next getState() re-reads from storage, then refresh the header badges.

  window.addEventListener("storage", function (e) {
    if (e.key === V2_KEY) {
      _state = null; // force re-read on next getState()
      refreshHeader();
    }
  });

  // ---------------------------------------------------------------- public API

  window.BKCart = {
    // State
    getState:     getState,
    setState:     setState,
    // Lines
    getLines:     getLines,
    upsertLine:   upsertLine,
    updateLine:   updateLine,
    removeLine:   removeLine,
    clearCart:    clearCart,
    totals:       totals,
    // Day / slot / pay
    getDayIso:    getDayIso,
    setDayIso:    setDayIso,
    getSlot:      getSlot,
    setSlot:      setSlot,
    getSlotId:    getSlotId,
    setSlotId:    setSlotId,
    getPay:       getPay,
    setPay:       setPay,
    // Formatting
    rands:        rands,
    refreshHeader: refreshHeader,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refreshHeader);
  } else {
    refreshHeader();
  }
})();
