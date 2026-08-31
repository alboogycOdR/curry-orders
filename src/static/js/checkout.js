// checkout.js — the Checkout screen (PR 4).
// Cart v2: uses BKCart.getLines() / getDayIso() / getSlotId() / etc.
// cartToLines() now sends kitchen_note per line (KD-5).
// Recovery: slot_full / dish_unavailable / dish_qty_exceeded still work;
// line references now use getLines() index rather than Object.keys order.
(function () {
  "use strict";

  function readJSONScript(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try { return JSON.parse(el.textContent); } catch (e) { return fallback; }
  }

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
  }

  function getCookie(name) {
    var prefix = name + "=";
    var parts = document.cookie ? document.cookie.split("; ") : [];
    for (var i = 0; i < parts.length; i++) {
      if (parts[i].indexOf(prefix) === 0)
        return decodeURIComponent(parts[i].slice(prefix.length));
    }
    return null;
  }

  // v2 cartToLines: reads getLines(), sends kitchen_note (KD-5).
  function cartToLines() {
    return window.BKCart.getLines().map(function (l) {
      return {
        dish_id:          l.itemId,
        quantity:         l.qty,
        option_value_ids: l.optionValueIds || [],
        kitchen_note:     (l.notes || "").slice(0, 80),
      };
    });
  }

  function makeIdempotencyKey() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "ck-" + Date.now() + "-" + Math.random().toString(36).slice(2);
  }
  var idempotencyKey = makeIdempotencyKey();

  document.addEventListener("DOMContentLoaded", function () {
    var days = readJSONScript("days-data", []);

    var payEft   = document.getElementById("ck-pay-eft");
    var payCash  = document.getElementById("ck-pay-cash");
    var nameInput    = document.getElementById("ck-name");
    var phoneInput   = document.getElementById("ck-phone");
    var noteInput    = document.getElementById("ck-note");
    var acceptPoliciesInput = document.getElementById("ck-accept-policies");
    var sheetEl      = document.getElementById("ck-sheet");
    var totalEl      = document.getElementById("ck-total-value");
    var collectDayEl = document.getElementById("ck-collect-day");
    var collectSlotEl= document.getElementById("ck-collect-slot");
    var placeBtn     = document.getElementById("ck-place");
    var placeBlockedReasonEl = document.getElementById("ck-place-blocked-reason");
    var formState    = document.getElementById("ck-form-state");
    var confirmedState= document.getElementById("ck-confirmed-state");
    var confirmHeading= document.getElementById("ck-confirm-heading");
    var confirmCopy  = document.getElementById("ck-confirm-copy");
    var refEl        = document.getElementById("ck-ref");
    var dayValueEl   = document.getElementById("ck-day-value");
    var totalValue2El= document.getElementById("ck-total-value-2");
    var startAnotherBtn= document.getElementById("ck-start-another");
    var viewOrderLink= document.getElementById("ck-view-order-link");
    var shareBtn     = document.getElementById("ck-share-link");
    var shareFallback= document.getElementById("ck-share-fallback");
    var shareInput   = document.getElementById("ck-share-input");
    var shareStatusEl= document.getElementById("ck-share-status");
    var redirectTimer= null;
    var formErrorEl  = document.getElementById("ck-form-error");
    var recoveryEl   = document.getElementById("ck-capacity-recovery");
    var fieldErrorEls = {
      name:           document.getElementById("ck-name-error"),
      mobile:         document.getElementById("ck-phone-error"),
      accept_policies:document.getElementById("ck-accept-policies-error"),
    };

    // currentDay(): resolve stored dayIso to a day entry
    function currentDay() {
      var iso = window.BKCart.getDayIso();
      if (!iso) return null;
      for (var i = 0; i < days.length; i++) {
        if (days[i].iso === iso) return days[i];
      }
      return null;
    }

    function titleCase(s) {
      return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
    }

    var payCashRow = document.getElementById("ck-pay-cash-row");
    var cashConfig = window.BK_CASH || { todayIso: null, available: false };

    function cashIsOfferable() {
      var day = currentDay();
      return cashConfig.available && !!day && day.iso === cashConfig.todayIso;
    }

    function renderPay() {
      var offerable = cashIsOfferable();
      if (payCashRow) payCashRow.hidden = !offerable;
      var pay = window.BKCart.getPay();
      if (pay === "cash" && !offerable) {
        pay = "eft";
        window.BKCart.setPay("eft");
      }
      payEft.checked = pay === "eft";
      payCash.checked = pay === "cash";
    }

    function clearErrors() {
      formErrorEl.hidden = true;
      formErrorEl.textContent = "";
      Object.keys(fieldErrorEls).forEach(function (k) {
        fieldErrorEls[k].hidden = true;
        fieldErrorEls[k].textContent = "";
      });
      recoveryEl.hidden = true;
      recoveryEl.innerHTML = "";
    }

    function showErrors(message, fields) {
      if (message) { formErrorEl.textContent = message; formErrorEl.hidden = false; }
      if (fields) {
        Object.keys(fields).forEach(function (k) {
          var el = fieldErrorEls[k];
          if (el) { el.textContent = fields[k]; el.hidden = false; }
        });
      }
    }

    // Capacity recovery (Monday-sprint Phase 1b, preserved in v2)
    function renderCapacityRecovery(errorCode, body) {
      recoveryEl.innerHTML = "";

      if (errorCode === "slot_full" && body.alternatives && body.alternatives.slots &&
          body.alternatives.slots.length) {
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
        var lines = window.BKCart.getLines();
        var line = typeof lineIndex === "number" ? (lines[lineIndex] || null) : null;
        if (line) {
          var p2 = document.createElement("p");
          p2.textContent = line.name + " — " + body.message;
          recoveryEl.appendChild(p2);
          var actions2 = document.createElement("div");
          actions2.className = "ck-recovery-actions";
          var removeBtn = document.createElement("button");
          removeBtn.type = "button";
          removeBtn.textContent = "Remove from my order";
          removeBtn.addEventListener("click", function () {
            window.BKCart.removeLine(line.id);
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
      var lines = window.BKCart.getLines();
      if (!lines.length) {
        sheetEl.innerHTML = '<p class="ck-sheet-empty">No items yet — <a href="' +
          window.BK_CHECKOUT_URLS.order + '">go back to the menu</a>.</p>';
      } else {
        var html = "";
        lines.forEach(function (l) {
          html +=
            '<div class="ck-sheet-line">' +
            '<span class="ck-sheet-qty">' + l.qty + "&times;</span>" +
            '<span class="ck-sheet-name">' + escapeHtml(l.name) +
            (l.heat ? " <span style=\"font-size:12px;opacity:.7;\">" + escapeHtml(l.heat) + "</span>" : "") +
            "</span>" +
            '<span class="ck-sheet-total">' + window.BKCart.rands(l.qty * l.unitPrice) + "</span>" +
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
      var lines = cartToLines(); // v2
      var payload = {
        name:           nameInput.value.trim(),
        mobile:         phoneInput.value.trim(),
        note:           noteInput ? noteInput.value.trim() : "",
        date:           day ? day.iso : null,
        slot_id:        slotId,
        payment_method: window.BKCart.getPay(),
        accept_policies: !!(acceptPoliciesInput && acceptPoliciesInput.checked),
        lines:          lines,
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
              showErrors((result.body && result.body.message) ||
                "Something went wrong placing your order — try again.");
              if (result.body && result.body.error) {
                renderCapacityRecovery(result.body.error, result.body);
              }
            }
            return;
          }

          window.BKCart.clearCart();
          window.BKCart.setSlot(null);
          window.BKCart.setSlotId(null);

          var order = result.body;
          refEl.textContent = order.order_number;
          confirmHeading.textContent = "We've got it. Order " + order.order_number + ".";
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
            button: shareBtn, fallback: shareFallback,
            input: shareInput, status: shareStatusEl,
            url: statusUrl,
            title: "Roti Connect — order " + order.order_number,
            onBeforeShare: function () {
              if (redirectTimer) { window.clearTimeout(redirectTimer); redirectTimer = null; }
            },
          });

          formState.hidden = true;
          confirmedState.hidden = false;
          confirmedState.scrollIntoView({ behavior: "smooth", block: "start" });

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

    renderPay();
    renderSheetAndTotals();
  });
})();
