// checkout.js — the Checkout screen (PR 4).
// Cart v2: uses BKCart.getLines() / getDayIso() / getSlotId() / etc.
// cartToLines() now sends kitchen_note per line (KD-5).
// Recovery: slot_full/closed: inline alternative-slot buttons that auto-
// resubmit; dish errors: highlight line + Remove action; day_full: show
// next_open_date; nonJson: distinct server-error state (Phase 1b).
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
    return safeGetLines().map(function (l) {
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

  // Phase 2c: safe BKCart wrappers — localStorage throws in private browsing
  // and when storage quota is exceeded; catch silently rather than crashing.
  function safeGetSlotId() { try { return window.BKCart.getSlotId(); } catch (e) { return null; } }
  function safeGetSlot() { try { return window.BKCart.getSlot(); } catch (e) { return null; } }
  function safeGetDayIso() { try { return window.BKCart.getDayIso(); } catch (e) { return null; } }
  function safeGetLines() { try { return window.BKCart.getLines(); } catch (e) { return []; } }
  function safeGetPay() { try { return window.BKCart.getPay(); } catch (e) { return "eft"; } }
  function safeSetSlotId(v) { try { window.BKCart.setSlotId(v); } catch (e) {} }
  function safeSetSlot(v) { try { window.BKCart.setSlot(v); } catch (e) {} }
  function safeSetDayIso(v) { try { window.BKCart.setDayIso(v); } catch (e) {} }
  function safeSetPay(v) { try { window.BKCart.setPay(v); } catch (e) {} }
  function safeClearCart() { try { window.BKCart.clearCart(); } catch (e) {} }
  function safeRemoveLine(id) { try { window.BKCart.removeLine(id); } catch (e) {} }

  document.addEventListener("DOMContentLoaded", function () {
    // Task 6 guard: redirect to /basket/ if cart is empty or no slot has
    // been selected. Prevents an empty "Collect —" state and ensures the
    // customer always arrives here with a real selection.
    if (!safeGetSlotId() || !safeGetLines().length) {
      window.location.replace(window.BK_CHECKOUT_URLS.basket);
      return;
    }

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
      var iso = safeGetDayIso();
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
      var pay = safeGetPay();
      if (pay === "cash" && !offerable) {
        pay = "eft";
        safeSetPay("eft");
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
      // Remove any line-error highlights from the sheet.
      var highlighted = sheetEl.querySelectorAll(".ck-sheet-line--error");
      for (var i = 0; i < highlighted.length; i++) {
        highlighted[i].classList.remove("ck-sheet-line--error");
      }
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

    // Phase 1b: capacity-error recovery rendered inline — no navigation away.
    // Name, mobile, note, and policy checkbox are never touched by this function
    // so they survive every retry path automatically.
    function renderCapacityRecovery(errorCode, body) {
      recoveryEl.innerHTML = "";

      // ---- slot_full / slot_closed: render alternatives inline ----
      if (errorCode === "slot_full" || errorCode === "slot_closed") {
        var p = document.createElement("p");
        p.textContent = body.message;
        recoveryEl.appendChild(p);

        var alts = Array.isArray(body.alternatives) && body.alternatives.length
          ? body.alternatives : [];

        if (alts.length) {
          var altsHint = document.createElement("p");
          altsHint.style.cssText = "margin: 8px 0 6px; font-size: 13px;";
          altsHint.textContent = "Available times — tap one to switch and retry:";
          recoveryEl.appendChild(altsHint);

          var actionsDiv = document.createElement("div");
          actionsDiv.className = "ck-recovery-actions";

          alts.forEach(function (alt) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.textContent = alt.label;
            btn.addEventListener("click", function () {
              safeSetSlotId(alt.id);
              safeSetSlot(alt.label);
              renderSheetAndTotals();
              // New idempotency key: different slot = different request body.
              idempotencyKey = makeIdempotencyKey();
              clearErrors();
              submitOrder();
            });
            actionsDiv.appendChild(btn);
          });

          recoveryEl.appendChild(actionsDiv);
        }

        // Last-resort: go back to basket to pick a slot manually.
        var backP = document.createElement("p");
        backP.style.cssText = "margin-top: 10px; font-size: 13px;";
        backP.innerHTML =
          'Or <a href="' + window.BK_CHECKOUT_URLS.basket +
          '">go back to choose a different time</a>.';
        recoveryEl.appendChild(backP);
        recoveryEl.hidden = false;
        return;
      }

      // ---- dish_unavailable / dish_qty_exceeded: highlight line + Remove ----
      if (errorCode === "dish_unavailable" || errorCode === "dish_qty_exceeded") {
        var lineIndex = body.line_index;
        var lines = window.BKCart.getLines();
        var line = typeof lineIndex === "number" ? (lines[lineIndex] || null) : null;

        // Highlight the specific sheet line.
        if (typeof lineIndex === "number") {
          var lineEl = sheetEl.querySelector('[data-line-index="' + lineIndex + '"]');
          if (lineEl) lineEl.classList.add("ck-sheet-line--error");
        }

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
            safeRemoveLine(line.id);
            // New idempotency key: different lines = different request body.
            idempotencyKey = makeIdempotencyKey();
            clearErrors();
            renderSheetAndTotals();
            // renderSheetAndTotals already shows the empty-basket state with a
            // menu link, so no extra handling needed here.
          });
          actions2.appendChild(removeBtn);
          recoveryEl.appendChild(actions2);
          recoveryEl.hidden = false;
          return;
        }
      }

      // ---- day_full: show next_open_date and link to change date ----
      if (errorCode === "day_full") {
        var nextRaw = body.next_open_date;
        var nextFormatted = nextRaw;
        try {
          // Parse as local midnight to avoid UTC-offset day-shift.
          var d = new Date(nextRaw + "T00:00:00");
          nextFormatted = d.toLocaleDateString("en-ZA", {
            weekday: "long", year: "numeric", month: "long", day: "numeric",
          });
        } catch (e) {}

        var p4 = document.createElement("p");
        p4.textContent =
          "This day is fully booked. The next available day is " + nextFormatted + ".";
        recoveryEl.appendChild(p4);

        var actions4 = document.createElement("div");
        actions4.className = "ck-recovery-actions";
        var changeA = document.createElement("a");
        changeA.href = window.BK_CHECKOUT_URLS.basket;
        changeA.textContent = "Go back and change your date";
        // Style to match the button look used by sibling recovery actions.
        changeA.style.cssText =
          "font-family:var(--font-body);font-size:13px;padding:7px 12px;" +
          "border:1px solid var(--color-text);background:none;cursor:pointer;" +
          "text-decoration:none;display:inline-block;";
        actions4.appendChild(changeA);
        recoveryEl.appendChild(actions4);
        recoveryEl.hidden = false;
        return;
      }

      // ---- cash_not_allowed / cash_cap: switch to EFT ----
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
          safeSetPay("eft");
          clearErrors();
          renderPay();
        });
        actions3.appendChild(switchBtn);
        recoveryEl.appendChild(actions3);
        recoveryEl.hidden = false;
      }
    }

    function renderSheetAndTotals() {
      var lines = safeGetLines();
      if (!lines.length) {
        sheetEl.innerHTML =
          '<p class="ck-sheet-empty">Your order is empty &mdash; ' +
          '<a href="' + window.BK_CHECKOUT_URLS.order + '">back to the menu</a>.</p>';
      } else {
        var html = "";
        lines.forEach(function (l, i) {
          html +=
            '<div class="ck-sheet-line" data-line-index="' + i + '">' +
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
      var slot = safeGetSlot();
      collectDayEl.textContent = day ? titleCase(day.long) : "—";
      collectSlotEl.textContent = slot || "—";

      // Task 6: also update the prominent collect summary block at the top.
      var summaryDayEl = document.getElementById("ck-collect-summary-day");
      var summarySlotEl = document.getElementById("ck-collect-summary-slot");
      if (summaryDayEl) summaryDayEl.textContent = day ? titleCase(day.long) : "—";
      if (summarySlotEl) summarySlotEl.textContent = slot || "—";

      var ready = t.count > 0 && !!slot && !!safeGetSlotId();
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
      if (payEft.checked) safeSetPay("eft");
    });
    payCash.addEventListener("change", function () {
      if (payCash.checked) safeSetPay("cash");
    });

    function setPlacing(placing) {
      placeBtn.disabled = placing;
      placeBtn.textContent = placing ? "Placing your order…" : "Place the order";
    }

    // submitOrder: extracted so alternative-slot buttons can auto-resubmit
    // without going through the click handler's disabled-check guard.
    // Name, mobile, note, and policy checkbox are read fresh from the DOM each
    // time so their values are always preserved through retries.
    function submitOrder() {
      var day = currentDay();
      var slotId = safeGetSlotId();
      var lines = cartToLines();
      // Safety guard: do not submit if state is no longer valid.
      // day is null when dayIso was never persisted to localStorage (old carts
      // that pre-date the basket.js seed fix). Show a friendly redirect message
      // rather than a cryptic "Some fields need attention" server error.
      if (!day || !slotId || !lines.length) {
        if (!day) {
          showErrors("Please go back to your basket and choose a collection day before placing your order.", {});
        }
        return;
      }

      var payload = {
        name:            nameInput.value.trim(),
        mobile:          phoneInput.value.trim(),
        note:            noteInput ? noteInput.value.trim() : "",
        date:            day ? day.iso : null,
        slot_id:         slotId,
        payment_method:  safeGetPay(),
        accept_policies: !!(acceptPoliciesInput && acceptPoliciesInput.checked),
        lines:           lines,
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
          // Phase 1b: Content-Type guard — non-JSON responses from the server
          // (error pages, proxy errors, etc.) get a distinct message that does
          // not look like the connection-failure copy in the .catch() handler.
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
              // Distinct server-error state — not the same copy as the network
              // error below.
              showErrors(
                "Something went wrong on our end — please try again or call us."
              );
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

          safeClearCart();
          safeSetSlot(null);
          safeSetSlotId(null);

          var order = result.body;

          // Task 8: persist last order for the Repeat module on Home /
          // Account. Guests don't have a session, so localStorage is the
          // right place; logged-in customers get it from the DB too.
          try {
            localStorage.setItem("rc_last_order_v1", JSON.stringify({
              order_number: order.order_number,
              public_token: order.public_token,
              reorder_url: window.BK_CHECKOUT_URLS.reorder.replace(
                "TOKEN_PLACEHOLDER", order.public_token
              ),
            }));
          } catch (e) {}
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
    }

    placeBtn.addEventListener("click", function () {
      if (placeBtn.disabled) return;
      clearErrors();
      submitOrder();
    });

    startAnotherBtn.addEventListener("click", function () {
      safeClearCart();
      safeSetSlot(null);
      safeSetSlotId(null);
      window.location.href = window.BK_CHECKOUT_URLS.order;
    });

    // ---- Phase 2c: inline slot-change panel ----

    var changeTimeBtn = document.getElementById("ck-change-time-btn");
    var slotPanel     = document.getElementById("ck-slot-panel");
    var slotDayBar    = document.getElementById("ck-slot-day-bar");
    var slotGridEl    = document.getElementById("ck-slot-grid");
    var slotCancelBtn = document.getElementById("ck-slot-cancel");
    var slotStatusEl  = document.getElementById("ck-slot-status");

    // Track which day ISO is currently selected inside the panel.
    var panelDayIso = null;
    // Prevent stale fetch responses from clobbering a newer request.
    var slotFetchSeq = 0;

    function announce(msg) {
      if (!slotStatusEl) return;
      slotStatusEl.textContent = "";
      // Briefly clear so that screen readers re-announce identical strings.
      setTimeout(function () { slotStatusEl.textContent = msg; }, 50);
    }

    function buildDayChipsHtml() {
      if (!days.length) return "";
      return days.map(function (d) {
        var selected = d.iso === panelDayIso ? " is-selected" : "";
        return '<button type="button" class="ck-slot-day-chip' + selected + '"' +
          ' data-day-iso="' + escapeHtml(d.iso) + '"' +
          ' data-day-long="' + escapeHtml(d.long) + '">' +
          '<span class="ck-chip-top">' + escapeHtml(d.dow) + "</span>" +
          '<span class="ck-chip-bottom">' + escapeHtml(d.dom) + "</span>" +
          "</button>";
      }).join("");
    }

    function buildSlotChipsHtml(slots) {
      if (!slots || !slots.length) {
        return '<p style="font-size:14px;color:var(--color-neutral-600);grid-column:1/-1">No slots available for this day.</p>';
      }
      return slots.map(function (s) {
        var fullClass = s.full ? " is-full" : "";
        return '<button type="button" class="ck-slot-chip' + fullClass + '"' +
          ' data-slot-id="' + escapeHtml(String(s.id)) + '"' +
          ' data-slot="' + escapeHtml(s.label) + '"' +
          (s.full ? " disabled" : "") + ">" +
          escapeHtml(s.label) + "</button>";
      }).join("");
    }

    function fetchSlotsForDay(iso, dayLong) {
      var seq = ++slotFetchSeq;
      slotGridEl.innerHTML = '<p style="font-size:14px;color:var(--color-neutral-600);grid-column:1/-1">Loading…</p>';
      var url = window.BK_CHECKOUT_URLS.api_day.replace("DATE_PLACEHOLDER", encodeURIComponent(iso));
      fetch(url, { credentials: "same-origin" })
        .then(function (resp) {
          if (!resp.ok) throw new Error("non-ok");
          return resp.json();
        })
        .then(function (body) {
          if (seq !== slotFetchSeq) return; // stale
          slotGridEl.innerHTML = buildSlotChipsHtml(body.slots || []);
          announce("Showing slots for " + titleCase(dayLong));
        })
        .catch(function () {
          if (seq !== slotFetchSeq) return;
          slotGridEl.innerHTML = '<p style="font-size:14px;color:var(--color-neutral-600);grid-column:1/-1">Couldn\'t load slots — try again.</p>';
        });
    }

    function openSlotPanel() {
      // Initialise panel day to the current cart day.
      var cartDay = currentDay();
      panelDayIso = cartDay ? cartDay.iso : (days.length ? days[0].iso : null);
      slotDayBar.innerHTML = buildDayChipsHtml();
      slotPanel.hidden = false;
      if (changeTimeBtn) changeTimeBtn.setAttribute("aria-expanded", "true");
      if (panelDayIso) {
        var cartDayLong = cartDay ? cartDay.long : (days[0] ? days[0].long : "");
        fetchSlotsForDay(panelDayIso, cartDayLong);
      }
    }

    function closeSlotPanel() {
      slotPanel.hidden = true;
      if (changeTimeBtn) {
        changeTimeBtn.setAttribute("aria-expanded", "false");
        changeTimeBtn.focus();
      }
    }

    if (changeTimeBtn) {
      changeTimeBtn.addEventListener("click", openSlotPanel);
    }

    if (slotCancelBtn) {
      slotCancelBtn.addEventListener("click", closeSlotPanel);
    }

    // Day chip click inside the panel.
    if (slotDayBar) {
      slotDayBar.addEventListener("click", function (e) {
        var chip = e.target.closest(".ck-slot-day-chip");
        if (!chip) return;
        var iso  = chip.getAttribute("data-day-iso");
        var long = chip.getAttribute("data-day-long") || iso;
        if (iso === panelDayIso) return; // already selected
        panelDayIso = iso;
        // Update selected state on chips.
        slotDayBar.querySelectorAll(".ck-slot-day-chip").forEach(function (c) {
          c.classList.toggle("is-selected", c.getAttribute("data-day-iso") === iso);
        });
        fetchSlotsForDay(iso, long);
      });
    }

    // Slot chip click inside the panel.
    if (slotGridEl) {
      slotGridEl.addEventListener("click", function (e) {
        var chip = e.target.closest(".ck-slot-chip");
        if (!chip || chip.disabled) return;
        var slotId    = chip.getAttribute("data-slot-id");
        var slotLabel = chip.getAttribute("data-slot");

        safeSetSlotId(slotId);
        safeSetSlot(slotLabel);

        // Update day in cart if the panel day differs from the stored day.
        if (panelDayIso && panelDayIso !== safeGetDayIso()) {
          safeSetDayIso(panelDayIso);
        }

        idempotencyKey = makeIdempotencyKey();
        renderSheetAndTotals();
        renderPay();
        closeSlotPanel();

        var dayLabel = "";
        for (var i = 0; i < days.length; i++) {
          if (days[i].iso === panelDayIso) { dayLabel = titleCase(days[i].long); break; }
        }
        announce("Collection time changed to " + dayLabel + " at " + slotLabel);
      });
    }

    // ---- Phase 2c: cross-tab cart sync via storage event ----
    // When another tab updates the cart key, re-read and refresh the view.
    window.addEventListener("storage", function (e) {
      if (e.key === "rc_cart_v2") {
        renderSheetAndTotals();
        renderPay();
      }
    });

    renderPay();
    renderSheetAndTotals();
  });
})();
