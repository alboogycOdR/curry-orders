// checkout.js — the Checkout screen (design handoff §"Screens" §3).
// Two states (payment form, then a confirmed receipt) toggled in place.
// "Place the order" now really does call `POST /api/checkout`
// (public/api.py, milestone 3, §11.6/§17.3) and creates a real
// `core.Order` row via `core.capacity.reserve()` — the confirmed state
// below shows the real order number/token the server assigned, not a
// fabricated reference; on success it hands the customer off to the real
// `/orders/:public_token/` page instead of just toggling in place, since
// that URL is the one worth bookmarking/reloading.
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

  // Reads the `csrftoken` cookie Django's CsrfViewMiddleware sets once
  // `{% csrf_token %}` is rendered anywhere on the page (checkout.html
  // does) — the standard "AJAX and CSRF" pattern from Django's own docs,
  // since this is a fetch() POST, not a plain form submit picking up the
  // hidden input Django also rendered.
  function getCookie(name) {
    var prefix = name + "=";
    var parts = document.cookie ? document.cookie.split("; ") : [];
    for (var i = 0; i < parts.length; i++) {
      if (parts[i].indexOf(prefix) === 0) {
        return decodeURIComponent(parts[i].slice(prefix.length));
      }
    }
    return null;
  }

  // A cart line's id is a dish id, or (dish.js's composite key)
  // "dishId:optId1,optId2" — split it back into what the API wants.
  function parseLineKey(key) {
    var parts = String(key).split(":");
    var dishId = parseInt(parts[0], 10);
    var optionValueIds = parts[1]
      ? parts[1].split(",").map(function (s) { return parseInt(s, 10); })
      : [];
    return { dishId: dishId, optionValueIds: optionValueIds };
  }

  function cartToLines(cart) {
    return Object.keys(cart).map(function (id) {
      var parsed = parseLineKey(id);
      return {
        dish_id: parsed.dishId,
        quantity: cart[id].qty,
        option_value_ids: parsed.optionValueIds,
      };
    });
  }

  // One per page load — an Idempotency-Key is only meant to dedupe
  // retries of the *same* attempt (a double-click, a flaky connection
  // the browser retries), not every attempt a customer ever makes here.
  function makeIdempotencyKey() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "ck-" + Date.now() + "-" + Math.random().toString(36).slice(2);
  }
  var idempotencyKey = makeIdempotencyKey();

  document.addEventListener("DOMContentLoaded", function () {
    var days = readJSONScript("days-data", []);

    var payEft = document.getElementById("ck-pay-eft");
    var payCash = document.getElementById("ck-pay-cash");
    var nameInput = document.getElementById("ck-name");
    var phoneInput = document.getElementById("ck-phone");
    var noteInput = document.getElementById("ck-note");
    var acceptPoliciesInput = document.getElementById("ck-accept-policies");
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
    var viewOrderLink = document.getElementById("ck-view-order-link");
    var formErrorEl = document.getElementById("ck-form-error");
    var fieldErrorEls = {
      name: document.getElementById("ck-name-error"),
      mobile: document.getElementById("ck-phone-error"),
      accept_policies: document.getElementById("ck-accept-policies-error"),
    };

    function currentDay() {
      var idx = window.BKCart.getDay();
      return days[idx] || null;
    }

    function titleCase(s) {
      return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
    }

    var payCashRow = document.getElementById("ck-pay-cash-row");
    var cashConfig = window.BK_CASH || { todayIso: null, available: false };

    // §20's "cash hidden on advance dates and when cap reached" — the
    // day picker lives on the order screen (order.js), one page back,
    // so this page re-derives "is the chosen day today" on every render
    // rather than trusting whatever was true when the page first loaded.
    function cashIsOfferable() {
      var day = currentDay();
      return cashConfig.available && !!day && day.iso === cashConfig.todayIso;
    }

    function renderPay() {
      var offerable = cashIsOfferable();
      if (payCashRow) payCashRow.hidden = !offerable;
      var pay = window.BKCart.getPay();
      if (pay === "cash" && !offerable) {
        // The chosen day changed (or cash filled up) since "cash" was
        // picked — fall back to EFT rather than leave a hidden radio
        // silently checked. reserve() would refuse a stale cash choice
        // anyway (§8.2's own cash_not_allowed/cash_cap ceilings), but
        // there's no reason to let the form say "cash" when the button
        // for it is gone.
        pay = "eft";
        window.BKCart.setPay("eft");
      }
      payEft.checked = pay === "eft";
      payCash.checked = pay === "cash";
    }

    function clearErrors() {
      formErrorEl.hidden = true;
      formErrorEl.textContent = "";
      Object.keys(fieldErrorEls).forEach(function (key) {
        fieldErrorEls[key].hidden = true;
        fieldErrorEls[key].textContent = "";
      });
    }

    function showErrors(message, fields) {
      if (message) {
        formErrorEl.textContent = message;
        formErrorEl.hidden = false;
      }
      if (fields) {
        Object.keys(fields).forEach(function (key) {
          var el = fieldErrorEls[key];
          if (el) {
            el.textContent = fields[key];
            el.hidden = false;
          }
        });
      }
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

      var ready = t.count > 0 && !!slot && !!window.BKCart.getSlotId();
      placeBtn.disabled = !ready;
    }

    payEft.addEventListener("change", function () {
      if (payEft.checked) window.BKCart.setPay("eft");
    });
    payCash.addEventListener("change", function () {
      if (payCash.checked) window.BKCart.setPay("cash");
    });

    function setPlacing(placing) {
      placeBtn.disabled = placing;
      placeBtn.textContent = placing ? "Placing your order…" : "Place the order";
    }

    placeBtn.addEventListener("click", function () {
      if (placeBtn.disabled) return;
      clearErrors();

      var day = currentDay();
      var slotId = window.BKCart.getSlotId();
      var cart = window.BKCart.getCart();
      var payload = {
        name: nameInput.value.trim(),
        mobile: phoneInput.value.trim(),
        note: noteInput ? noteInput.value.trim() : "",
        date: day ? day.iso : null,
        slot_id: slotId,
        payment_method: window.BKCart.getPay(),
        accept_policies: !!(acceptPoliciesInput && acceptPoliciesInput.checked),
        lines: cartToLines(cart),
      };

      setPlacing(true);

      fetch(window.BK_CHECKOUT_URLS.api_checkout, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(payload),
        credentials: "same-origin",
      })
        .then(function (resp) {
          return resp.json().then(function (body) {
            return { ok: resp.ok, status: resp.status, body: body };
          });
        })
        .then(function (result) {
          setPlacing(false);
          if (!result.ok) {
            if (result.body && result.body.fields) {
              showErrors(result.body.message, result.body.fields);
            } else {
              showErrors((result.body && result.body.message) || "Something went wrong placing your order — try again.");
            }
            return;
          }

          // The reservation succeeded — this cart is spent regardless of
          // what happens next, so clear it before navigating away.
          window.BKCart.clearCart();
          window.BKCart.setSlot(null);
          window.BKCart.setSlotId(null);

          var order = result.body;
          refEl.textContent = order.order_number;
          confirmHeading.textContent = "We've got it. Order " + order.order_number + ".";
          // No SMS integration this pass (notifications/ is unbuilt) —
          // bank details and the payment countdown live on the order
          // page this redirects to next, not a text message.
          confirmCopy.textContent =
            payload.payment_method === "cash"
              ? "Bring your payment in cash. We start cooking once the kitchen confirms."
              : "Taking you to your order page for the bank details and payment countdown.";
          dayValueEl.textContent = day ? titleCase(day.long) : "—";
          totalValue2El.textContent = totalEl.textContent;
          viewOrderLink.href = window.BK_CHECKOUT_URLS.order_status.replace(
            "TOKEN_PLACEHOLDER", order.public_token
          );

          formState.hidden = true;
          confirmedState.hidden = false;
          confirmedState.scrollIntoView({ behavior: "smooth", block: "start" });

          // A moment for the customer to read the confirmation, then on
          // to the real order-status page (§6.1) — the URL worth
          // bookmarking/reloading, unlike this one-shot checkout screen.
          window.setTimeout(function () {
            window.location.href = window.BK_CHECKOUT_URLS.order_status.replace(
              "TOKEN_PLACEHOLDER", order.public_token
            );
          }, 1800);
        })
        .catch(function () {
          setPlacing(false);
          showErrors("Couldn't reach the server — check your connection and try again.");
        });
    });

    startAnotherBtn.addEventListener("click", function () {
      window.BKCart.clearCart();
      window.BKCart.setSlot(null);
      window.BKCart.setSlotId(null);
      window.location.href = window.BK_CHECKOUT_URLS.order;
    });

    renderPay();
    renderSheetAndTotals();
  });
})();
