// checkout.js — the Checkout screen (design handoff §"Screens" §3).
// Two states (payment form, then a confirmed receipt) toggled in place;
// see checkout.html's comment and public/views.py's module docstring for
// why "Place the order" fabricates a reference instead of creating a real
// `core.Order` — that's milestone 3 (§8.3's reservation transaction).
(function () {
  "use strict";

  function readJSONScript(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return fallback;
    }
  }

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var days = readJSONScript("days-data", []);

    var payEft = document.getElementById("ck-pay-eft");
    var payCash = document.getElementById("ck-pay-cash");
    var sheetEl = document.getElementById("ck-sheet");
    var totalEl = document.getElementById("ck-total-value");
    var collectDayEl = document.getElementById("ck-collect-day");
    var collectSlotEl = document.getElementById("ck-collect-slot");
    var placeBtn = document.getElementById("ck-place");
    var formState = document.getElementById("ck-form-state");
    var confirmedState = document.getElementById("ck-confirmed-state");
    var confirmHeading = document.getElementById("ck-confirm-heading");
    var confirmCopy = document.getElementById("ck-confirm-copy");
    var refEl = document.getElementById("ck-ref");
    var dayValueEl = document.getElementById("ck-day-value");
    var totalValue2El = document.getElementById("ck-total-value-2");
    var startAnotherBtn = document.getElementById("ck-start-another");

    function currentDay() {
      var idx = window.BKCart.getDay();
      return days[idx] || null;
    }

    function titleCase(s) {
      return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
    }

    function renderPay() {
      var pay = window.BKCart.getPay();
      payEft.checked = pay === "eft";
      payCash.checked = pay === "cash";
    }

    function renderSheetAndTotals() {
      var cart = window.BKCart.getCart();
      var ids = Object.keys(cart);
      if (ids.length === 0) {
        sheetEl.innerHTML = '<p class="ck-sheet-empty">No items yet — <a href="' +
          window.BK_CHECKOUT_URLS.order + '">go back to the menu</a>.</p>';
      } else {
        var html = "";
        ids.forEach(function (id) {
          var line = cart[id];
          html +=
            '<div class="ck-sheet-line">' +
            '<span class="ck-sheet-qty">' + line.qty + "&times;</span>" +
            '<span class="ck-sheet-name">' + escapeHtml(line.name) + "</span>" +
            '<span class="ck-sheet-total">' + window.BKCart.rands(line.qty * line.price) + "</span>" +
            "</div>";
        });
        sheetEl.innerHTML = html;
      }
      var t = window.BKCart.totals();
      totalEl.textContent = window.BKCart.rands(t.total);

      var day = currentDay();
      var slot = window.BKCart.getSlot();
      collectDayEl.textContent = day ? titleCase(day.long) : "—";
      collectSlotEl.textContent = slot || "—";

      var ready = t.count > 0 && !!slot;
      placeBtn.disabled = !ready;
    }

    payEft.addEventListener("change", function () {
      if (payEft.checked) window.BKCart.setPay("eft");
    });
    payCash.addEventListener("change", function () {
      if (payCash.checked) window.BKCart.setPay("cash");
    });

    placeBtn.addEventListener("click", function () {
      if (placeBtn.disabled) return;
      var t = window.BKCart.totals();
      var day = currentDay();
      var slot = window.BKCart.getSlot();
      var pay = window.BKCart.getPay();

      // Fabricated — real order numbers are `trading_days.next_order_seq`
      // under a row lock (D-04), assigned inside the reservation
      // transaction (§8.3), not generated in the browser.
      var ref = "DEMO-" + Math.floor(1000 + Math.random() * 9000);

      confirmHeading.textContent = "We've got it. Collection " + slot + ".";
      confirmCopy.textContent =
        pay === "cash"
          ? "Bring " + window.BKCart.rands(t.total) +
            " in cash. We start cooking once the kitchen confirms — you'll get an SMS either way."
          : "Bank details are on their way by SMS. Your slot is held for 45 minutes; cooking starts the moment the payment is verified.";
      refEl.textContent = ref;
      dayValueEl.textContent = day ? titleCase(day.long) : "—";
      totalValue2El.textContent = window.BKCart.rands(t.total);

      formState.hidden = true;
      confirmedState.hidden = false;
      confirmedState.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    startAnotherBtn.addEventListener("click", function () {
      window.BKCart.clearCart();
      window.BKCart.setSlot(null);
      window.location.href = window.BK_CHECKOUT_URLS.order;
    });

    renderPay();
    renderSheetAndTotals();
  });
})();
