// cart.js — the customer cart, held in the browser only.
//
// This is the "visual pass" stand-in for real cart state (see
// public/views.py's module docstring). Production milestone 3 replaces it
// with a session or a draft `core.Order` row held against a slot by
// `core.capacity.reserve()`; nothing here talks to the server. Cart lines
// are denormalised ({id, name, price, qty} per line, not just id -> qty)
// so any page can render totals/the header summary without also having
// the full menu price list loaded — order.js is the only script that
// needs the menu price map (to price a dish it doesn't yet have a line
// for), everything downstream reads what's already in the cart.
//
// Loaded on every page (base.html, `defer`), before any per-page script —
// order.js/checkout.js/kitchen.js all assume `window.BKCart` exists.
(function () {
  "use strict";

  var CART_KEY = "bk_cart_v1";
  var DAY_KEY = "bk_day_v1";
  var SLOT_KEY = "bk_slot_v1";
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

  function rands(n) {
    return "R " + Number(n).toFixed(2);
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
    if (t.count === 0) {
      el.textContent = "No order started";
    } else {
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
    getPay: getPay,
    setPay: setPay,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refreshHeader);
  } else {
    refreshHeader();
  }
})();
