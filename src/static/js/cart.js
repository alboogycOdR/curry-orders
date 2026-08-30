// cart.js — the customer cart, held in the browser only.
//
// A client-side staging area (see public/views.py's module docstring) —
// nothing here talks to the server until checkout.js turns it into one
// `POST /api/checkout` call, which runs the real `core.capacity.reserve()`
// transaction (core/capacity.py) server-side. Cart lines are denormalised
// ({id, name, price, qty} per line, not just id -> qty) so any page can
// render totals/the header summary without a second price lookup.
// `price` is always integer cents (`core.Dish.price_cents` plus any
// selected `DishOptionValue.price_delta_cents`) — never rands — matching
// how the backend stores money everywhere (core/money.py).
//
// Loaded on every page (base.html, `defer`), before any per-page script —
// order.js/checkout.js/kitchen.js all assume `window.BKCart` exists.
(function () {
  "use strict";

  var CART_KEY = "bk_cart_v1";
  var DAY_KEY = "bk_day_v1";
  var SLOT_KEY = "bk_slot_v1";
  var SLOT_ID_KEY = "bk_slot_id_v1";
  var PAY_KEY = "bk_pay_v1";

  function readJSON(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback; // private browsing / storage disabled — fail to empty, not to a thrown error
    }
  }
  function writeJSON(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      /* storage unavailable — state just won't persist across loads */
    }
  }
  function readStr(key) {
    try {
      return localStorage.getItem(key);
    } catch (e) {
      return null;
    }
  }
  function writeStr(key, value) {
    try {
      if (value === null || value === undefined) localStorage.removeItem(key);
      else localStorage.setItem(key, String(value));
    } catch (e) {
      /* ignore */
    }
  }

  // Mirrors core.money.format_cents exactly (space-separated thousands,
  // always two decimals) — `n` is integer cents, same unit as every
  // price this cart ever stores (dish rows' data-dish-price,
  // dish.js's data-base-price/data-delta are all `core.Dish.price_cents`/
  // `DishOptionValue.price_delta_cents`, never rands) — matches spec
  // §11.1's format and, more importantly, `core.money`'s own "integer
  // cents everywhere, never floats" rule from the backend side.
  function rands(cents) {
    var n = Math.round(Number(cents));
    var sign = n < 0 ? "-" : "";
    var abs = Math.abs(n);
    var wholeRand = Math.floor(abs / 100);
    var subCents = abs % 100;
    var grouped = String(wholeRand).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return sign + "R " + grouped + "." + (subCents < 10 ? "0" : "") + subCents;
  }

  function getCart() {
    return readJSON(CART_KEY, {});
  }

  function setCart(cart) {
    writeJSON(CART_KEY, cart);
    refreshHeader();
  }

  // Set (or clear, at qty<=0) one line. name/price are only needed the
  // first time a dish is added — bump() below re-reads them off the
  // existing line so a caller never has to pass the menu map around.
  function setLine(id, name, price, qty) {
    var cart = getCart();
    if (qty <= 0) delete cart[id];
    else cart[id] = { name: name, price: price, qty: qty };
    setCart(cart);
    return cart;
  }

  function bump(id, name, price, delta) {
    var cart = getCart();
    var current = cart[id] ? cart[id].qty : 0;
    return setLine(id, name, price, current + delta);
  }

  function clearCart() {
    setCart({});
  }

  function totals(cart) {
    cart = cart || getCart();
    var count = 0;
    var total = 0;
    Object.keys(cart).forEach(function (id) {
      count += cart[id].qty;
      total += cart[id].qty * cart[id].price;
    });
    return { count: count, total: total };
  }

  function refreshHeader() {
    var el = document.getElementById("cart-summary");
    if (!el) return;
    var t = totals();
    // Hidden rather than "No order started" on an empty cart -- a
    // customer just browsing the menu doesn't need to be told they
    // haven't ordered yet (they know), and it's noise on every page
    // until they've actually added something. Flagged directly by the
    // user. Shows up the moment there's a real item to summarise.
    if (t.count === 0) {
      el.hidden = true;
      el.textContent = "";
    } else {
      el.hidden = false;
      el.textContent =
        t.count + (t.count === 1 ? " item · " : " items · ") + rands(t.total);
    }
  }

  function getDay() {
    var v = readStr(DAY_KEY);
    return v === null ? 0 : parseInt(v, 10);
  }
  function setDay(i) {
    writeStr(DAY_KEY, i);
  }
  function getSlot() {
    return readStr(SLOT_KEY);
  }
  function setSlot(s) {
    writeStr(SLOT_KEY, s);
  }
  // The real Slot PK (checkout needs this — §17.3's POST /api/checkout
  // body takes slot_id, not a time label) alongside the label above,
  // which stays purely for display. Two keys, not one object, so
  // getSlot()'s existing shape (a bare string) doesn't change for
  // anything that only ever wanted the label.
  function getSlotId() {
    var v = readStr(SLOT_ID_KEY);
    return v === null ? null : parseInt(v, 10);
  }
  function setSlotId(id) {
    writeStr(SLOT_ID_KEY, id);
  }
  function getPay() {
    return readStr(PAY_KEY) || "eft";
  }
  function setPay(p) {
    writeStr(PAY_KEY, p);
  }

  window.BKCart = {
    getCart: getCart,
    setCart: setCart,
    setLine: setLine,
    bump: bump,
    clearCart: clearCart,
    totals: totals,
    rands: rands,
    refreshHeader: refreshHeader,
    getDay: getDay,
    setDay: setDay,
    getSlot: getSlot,
    setSlot: setSlot,
    getSlotId: getSlotId,
    setSlotId: setSlotId,
    getPay: getPay,
    setPay: setPay,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refreshHeader);
  } else {
    refreshHeader();
  }
})();
