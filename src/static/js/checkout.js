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

  // `keys` explicit (not re-derived internally via Object.keys(cart))
  // so the caller can keep the exact same array around afterward --
  // the server's `line_index` on a capacity error refers to a position
  // in *this* array, and re-computing Object.keys(cart) later isn't
  // guaranteed to reproduce the same order (integer-like string keys —
  // a plain dish id with no options — enumerate before non-integer
  // ones like "5:12,7", regardless of insertion order).
  function cartToLines(cart, keys) {
    return keys.map(function (id) {
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
    var placeBlockedReasonEl = document.getElementById("ck-place-blocked-reason");
    var formState = document.getElementById("ck-form-state");
    var confirmedState = document.getElementById("ck-confirmed-state");
    var confirmHeading = document.getElementById("ck-confirm-heading");
    var confirmCopy = document.getElementById("ck-confirm-copy");
    var refEl = document.getElementById("ck-ref");
    var dayValueEl = document.getElementById("ck-day-value");
    var totalValue2El = document.getElementById("ck-total-value-2");
    var startAnotherBtn = document.getElementById("ck-start-another");
    var viewOrderLink = document.getElementById("ck-view-order-link");
    var shareBtn = document.getElementById("ck-share-link");
    var shareFallback = document.getElementById("ck-share-fallback");
    var shareInput = document.getElementById("ck-share-input");
    var shareStatusEl = document.getElementById("ck-share-status");
    var redirectTimer = null;
    var formErrorEl = document.getElementById("ck-form-error");
    var recoveryEl = document.getElementById("ck-capacity-recovery");
    var lastSubmittedCartKeys = [];
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
      recoveryEl.hidden = true;
      recoveryEl.innerHTML = "";
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

    // Monday-sprint Phase 1b (docs/MONDAY_SPRINT.md): a capacity error
    // used to be a dead end -- "Back to the menu" was the only recovery
    // path, after the customer had already filled in the whole form.
    // This offers whatever the server actually computed a fix for; it
    // never invents a recovery option the response didn't send (e.g.
    // day_full's `alternatives` is currently always empty server-side —
    // core.capacity's own "not computed this pass" — so day_full just
    // falls through to the plain message, same as before).
    function renderCapacityRecovery(errorCode, body) {
      recoveryEl.innerHTML = "";

      if (errorCode === "slot_full" && body.alternatives && body.alternatives.slots
          && body.alternatives.slots.length) {
        var p = document.createElement("p");
        p.textContent = "That time filled up. Other collection times still open today:";
        recoveryEl.appendChild(p);
        var actions = document.createElement("div");
        actions.className = "ck-recovery-actions";
        body.alternatives.slots.forEach(function (alt) {
          var btn = document.createElement("button");
          btn.type = "button";
          btn.textContent = alt.label;
          btn.addEventListener("click", function () {
            window.BKCart.setSlot(alt.label);
            window.BKCart.setSlotId(alt.slot_id);
            clearErrors();
            renderSheetAndTotals();
          });
          actions.appendChild(btn);
        });
        recoveryEl.appendChild(actions);
        recoveryEl.hidden = false;
        return;
      }

      if (errorCode === "dish_unavailable" || errorCode === "dish_qty_exceeded") {
        var lineIndex = body.line_index;
        var cartKey = typeof lineIndex === "number" ? lastSubmittedCartKeys[lineIndex] : null;
        var cart = window.BKCart.getCart();
        var line = cartKey ? cart[cartKey] : null;
        if (line) {
          var p2 = document.createElement("p");
          // .textContent, not innerHTML -- no escaping needed, the
          // browser treats this as literal text either way.
          p2.textContent = line.name + " — " + body.message;
          recoveryEl.appendChild(p2);
          var actions2 = document.createElement("div");
          actions2.className = "ck-recovery-actions";
          var removeBtn = document.createElement("button");
          removeBtn.type = "button";
          removeBtn.textContent = "Remove from my order";
          removeBtn.addEventListener("click", function () {
            window.BKCart.setLine(cartKey, line.name, line.price, 0);
            clearErrors();
            renderSheetAndTotals();
          });
          actions2.appendChild(removeBtn);
          recoveryEl.appendChild(actions2);
          recoveryEl.hidden = false;
          return;
        }
      }

      if (errorCode === "cash_not_allowed" || errorCode === "cash_cap") {
        var p3 = document.createElement("p");
        p3.textContent = body.message;
        recoveryEl.appendChild(p3);
        var actions3 = document.createElement("div");
        actions3.className = "ck-recovery-actions";
        var switchBtn = document.createElement("button");
        switchBtn.type = "button";
        switchBtn.textContent = "Switch to EFT";
        switchBtn.addEventListener("click", function () {
          window.BKCart.setPay("eft");
          clearErrors();
          renderPay();
        });
        actions3.appendChild(switchBtn);
        recoveryEl.appendChild(actions3);
        recoveryEl.hidden = false;
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

      if (ready) {
        placeBlockedReasonEl.hidden = true;
      } else if (t.count === 0) {
        placeBlockedReasonEl.textContent =
          "Your order sheet is empty — add a dish from the menu first.";
        placeBlockedReasonEl.hidden = false;
      } else {
        placeBlockedReasonEl.textContent =
          "Choose a collection day and time window on the order page before placing your order.";
        placeBlockedReasonEl.hidden = false;
      }
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
      var cartKeys = Object.keys(cart);
      lastSubmittedCartKeys = cartKeys;
      var payload = {
        name: nameInput.value.trim(),
        mobile: phoneInput.value.trim(),
        note: noteInput ? noteInput.value.trim() : "",
        date: day ? day.iso : null,
        slot_id: slotId,
        payment_method: window.BKCart.getPay(),
        accept_policies: !!(acceptPoliciesInput && acceptPoliciesInput.checked),
        lines: cartToLines(cart, cartKeys),
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
          // A non-JSON failure (a proxy error page, an unhandled 500
          // with an HTML debug page, ...) used to reach resp.json()
          // anyway and degrade to a generic "couldn't reach the server"
          // message -- true-sounding but wrong, since the server *was*
          // reached, it just didn't answer the way this code expected.
          var contentType = resp.headers.get("Content-Type") || "";
          if (contentType.indexOf("application/json") === -1) {
            return { ok: false, status: resp.status, body: null, nonJson: true };
          }
          return resp.json().then(function (body) {
            return { ok: resp.ok, status: resp.status, body: body };
          });
        })
        .then(function (result) {
          setPlacing(false);
          if (!result.ok) {
            if (result.nonJson) {
              showErrors("Something went wrong on our end — try again in a moment.");
            } else if (result.body && result.body.fields) {
              showErrors(result.body.message, result.body.fields);
            } else {
              showErrors((result.body && result.body.message) || "Something went wrong placing your order — try again.");
              if (result.body && result.body.error) {
                renderCapacityRecovery(result.body.error, result.body);
              }
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
          var statusUrl = window.location.origin + window.BK_CHECKOUT_URLS.order_status.replace(
            "TOKEN_PLACEHOLDER", order.public_token
          );
          viewOrderLink.href = statusUrl;

          window.BKShareLink.wire({
            button: shareBtn,
            fallback: shareFallback,
            input: shareInput,
            status: shareStatusEl,
            url: statusUrl,
            title: "Brandon's Kitchen — order " + order.order_number,
            onBeforeShare: function () {
              // Whichever tier fires, the customer is actively engaging
              // with this screen — don't yank them off it via the 1.8s
              // auto-redirect mid-interaction.
              if (redirectTimer) {
                window.clearTimeout(redirectTimer);
                redirectTimer = null;
              }
            },
          });

          formState.hidden = true;
          confirmedState.hidden = false;
          confirmedState.scrollIntoView({ behavior: "smooth", block: "start" });

          // A moment for the customer to read the confirmation, then on
          // to the real order-status page (§6.1) — the URL worth
          // bookmarking/reloading, unlike this one-shot checkout screen.
          // Cancelled if they interact with Copy/share instead (below) —
          // 1.8s isn't enough time to actually use that button before
          // being yanked off the page.
          redirectTimer = window.setTimeout(function () {
            window.location.href = statusUrl;
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

    // share-link.js — see that file's own header for the fallback chain.
    // Wired once the real order/statusUrl are known (inside the
    // successful-checkout .then() above), not here at page load.

    renderPay();
    renderSheetAndTotals();
  });
})();
