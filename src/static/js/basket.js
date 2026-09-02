// basket.js — Basket screen (PR 5). Day chips, slot grid, line steppers, edit.
//
// Cart v2 API: getDayIso()/setDayIso(), getSlot()/setSlot(), getSlotId()/setSlotId(),
// getLines(), updateLine(), removeLine(), totals(), rands().
// Edit mode: BKItemSheet.openEdit(lineId, itemId) — dispatches bkItemSheet:updated.
// Continue disabled until cart non-empty AND a live slot is selected.
// Empty state: replaces grid with brief message + browse link; no Total, no Place order.
(function () {
  "use strict";

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
  }

  function readJSONScript(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try { return JSON.parse(el.textContent); } catch (e) { return fallback; }
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Task 6: show a toast if checkout.js redirected here with a message
    // (e.g. slot_full). The message is stored in sessionStorage so it
    // survives the redirect without appearing as a query param in the URL.
    var toastEl = document.getElementById("bk-toast");
    if (toastEl) {
      try {
        var pendingToast = sessionStorage.getItem("rc_basket_toast");
        if (pendingToast) {
          sessionStorage.removeItem("rc_basket_toast");
          toastEl.textContent = pendingToast;
          toastEl.hidden = false;
          window.setTimeout(function () { if (toastEl) toastEl.hidden = true; }, 7000);
        }
      } catch (e) {}
    }

    var days         = readJSONScript("bk-days-data", []);
    var eftHold      = readJSONScript("bk-eft-hold-data", 30);

    var emptyEl      = document.getElementById("bk-empty");
    var contentEl    = document.getElementById("bk-content");
    var linesEl      = document.getElementById("bk-lines");
    var dayChipsEl   = document.getElementById("bk-day-chips");
    var slotGridEl   = document.getElementById("bk-slot-grid");
    var slotNoteEl   = document.getElementById("bk-slot-note");
    var totalRowEl   = document.getElementById("bk-total-row");
    var totalValueEl = document.getElementById("bk-total-value");
    var continueBtn  = document.getElementById("bk-continue");
    var readyHintEl  = document.getElementById("bk-ready-hint");
    var dateNoticeEl = document.getElementById("bk-date-notice");

    // Catalog from #menu-data for Edit sheet and sold-out check.
    var catalog = readJSONScript("menu-data", []);
    var catalogById = {};
    catalog.forEach(function (item) { catalogById[item.id] = item; });

    // Resolve stored dayIso to an index in the orderable list (default 0).
    var storedDayIso = window.BKCart.getDayIso();
    var initialDayIndex = 0;
    if (storedDayIso) {
      var _dayFound = false;
      for (var di = 0; di < days.length; di++) {
        if (days[di].iso === storedDayIso) { initialDayIndex = di; _dayFound = true; break; }
      }
      // Stored day is no longer orderable (cutoff passed overnight) — reset to
      // first available. Without this the customer sees the first chip highlighted
      // while checkout.js returns null for currentDay(), creating a silent deadlock.
      if (!_dayFound) storedDayIso = null;
    }

    var state = {
      dayIndex: initialDayIndex,
      dayIso:   storedDayIso || (days[0] ? days[0].iso : null),
      slot:     window.BKCart.getSlot(),
      slotId:   window.BKCart.getSlotId(),
    };

    // Seed or correct localStorage day so checkout.js always reads a valid value.
    if (!storedDayIso && state.dayIso) {
      window.BKCart.setDayIso(state.dayIso);
    }

    var loadRequestId = 0;

    // ---- render helpers ----

    function renderDayChips() {
      dayChipsEl.querySelectorAll("[data-day-index]").forEach(function (btn) {
        var idx = parseInt(btn.getAttribute("data-day-index"), 10);
        btn.classList.toggle("is-selected", idx === state.dayIndex);
      });
    }

    function buildSlotGridHtml(slots) {
      if (!slots.length) return '<p style="font-size:14px;color:var(--color-neutral-600)">No slots available for this day.</p>';
      return slots.map(function (s) {
        return '<button type="button" class="bk-chip bk-slot-chip' + (s.full ? " is-full" : "") +
          '" data-slot-id="' + s.id + '" data-slot="' + escapeHtml(s.label) + '"' +
          (s.full ? " disabled" : "") + ">" + escapeHtml(s.label) + "</button>";
      }).join("");
    }

    function renderSlotGrid() {
      slotGridEl.querySelectorAll(".bk-slot-chip").forEach(function (btn) {
        var sid = parseInt(btn.getAttribute("data-slot-id"), 10);
        btn.classList.toggle("is-selected", !btn.disabled && sid === state.slotId);
      });
      slotNoteEl.textContent = state.slot
        ? "Held for " + eftHold + " minutes once you place the order."
        : "Pick a collection window — some may already be full.";
    }

    function renderLines() {
      var lines = window.BKCart.getLines();

      if (!lines.length) {
        emptyEl.hidden = false;
        contentEl.hidden = true;
        return;
      }
      emptyEl.hidden = true;
      contentEl.hidden = false;

      var html = "";
      lines.forEach(function (line) {
        var catalogItem = catalogById[line.itemId];
        var canEdit = catalogItem && !catalogItem.sold_out;

        // Build option label: heat first, then extras
        var optParts = [];
        if (line.heat) optParts.push(escapeHtml(line.heat));
        if (line.extras && line.extras.length) {
          line.extras.forEach(function (ex) { optParts.push(escapeHtml(ex.name)); });
        }

        // Strip "(Heat, Extra)" suffix that may already be baked into line.name
        var displayName = escapeHtml(line.name.replace(/ \([^)]*\)$/, ""));

        html +=
          '<div class="bk-line" data-line-id="' + escapeHtml(line.id) + '">' +
          '<div class="bk-line-info">' +
          '<div class="bk-line-name">' + displayName + "</div>" +
          (optParts.length ? '<div class="bk-line-opts">' + optParts.join(" · ") + "</div>" : "") +
          (line.notes ? '<div class="bk-line-note">' + escapeHtml(line.notes) + "</div>" : "") +
          "</div>" +
          '<div class="bk-line-right">' +
          '<div class="bk-stepper">' +
          '<button type="button" class="btn btn-secondary bk-stepper-btn" ' +
            'data-action="decrement" data-line-id="' + escapeHtml(line.id) + '" aria-label="Remove one">&minus;</button>' +
          '<span class="bk-stepper-count">' + line.qty + "</span>" +
          '<button type="button" class="btn btn-secondary bk-stepper-btn" ' +
            'data-action="increment" data-line-id="' + escapeHtml(line.id) + '" aria-label="Add one">+</button>' +
          "</div>" +
          '<div class="bk-line-total">' + window.BKCart.rands(line.qty * line.unitPrice) + "</div>" +
          (canEdit
            ? '<button type="button" class="btn btn-ghost bk-edit-btn" ' +
              'data-action="edit" data-line-id="' + escapeHtml(line.id) + '" data-item-id="' + line.itemId + '">Edit</button>'
            : "") +
          "</div>" +
          "</div>";
      });
      linesEl.innerHTML = html;
    }

    function renderTotalAndContinue() {
      var t = window.BKCart.totals();
      var ready = t.count > 0 && !!state.slot;

      if (totalRowEl) totalRowEl.hidden = t.count === 0;
      if (totalValueEl && t.count > 0) totalValueEl.textContent = window.BKCart.rands(t.total);

      if (continueBtn) continueBtn.disabled = !ready;

      if (readyHintEl) {
        if (ready) {
          var day = days[state.dayIndex];
          readyHintEl.textContent = "Slot " + state.slot + ", " + (day ? day.long : "") + ".";
        } else if (t.count > 0) {
          readyHintEl.textContent = "Pick a collection window to continue.";
        } else {
          readyHintEl.textContent = "";
        }
      }
    }

    function renderAll() {
      renderLines();
      renderDayChips();
      renderSlotGrid();
      renderTotalAndContinue();
    }

    // ---- date notice ----

    function showDateNotice(msg) {
      if (!dateNoticeEl) return;
      dateNoticeEl.textContent = msg;
      dateNoticeEl.hidden = false;
    }
    function clearDateNotice() {
      if (!dateNoticeEl) return;
      dateNoticeEl.textContent = "";
      dateNoticeEl.hidden = true;
    }

    // ---- prune cart for a new day's availability ----

    function pruneCartForCategories(categories) {
      var available = {};
      categories.forEach(function (cat) {
        (cat.dishes || []).forEach(function (dish) {
          if (!dish.sold_out) available[dish.id] = true;
        });
      });
      var removed = [];
      var currentLines = window.BKCart.getLines().slice();
      currentLines.forEach(function (l) {
        if (!available[l.itemId]) {
          removed.push(l.name);
          window.BKCart.removeLine(l.id);
        }
      });
      return removed;
    }

    // ---- day load (fetch) ----

    // preserveSlot: true when called on initial load for the already-stored day
    // (customer revisits /basket/ with a saved slot); false on an explicit day-chip
    // click (old slot no longer relevant — clear it immediately).
    function loadDay(dayIndex, preserveSlot) {
      var day = days[dayIndex];
      if (!day) return;

      // Remember the current slot so we can try to restore it after fetch
      // (only when preserveSlot is true — i.e. initial load, not a day change).
      var prevSlotId = preserveSlot ? state.slotId : null;

      // Clear slot immediately — will be restored below if the chip is still open.
      state.slot = null;
      state.slotId = null;
      window.BKCart.setSlot(null);
      window.BKCart.setSlotId(null);
      clearDateNotice();
      renderSlotGrid();
      renderTotalAndContinue();

      var requestId = ++loadRequestId;
      var url = window.BK_BASKET_URLS.api_availability + "?date=" + encodeURIComponent(day.iso);
      fetch(url, { credentials: "same-origin" })
        .then(function (resp) {
          if (resp.ok) return resp.json();
          return resp.json().then(function (body) {
            // outside_horizon: date is no longer orderable
            var err = { _error: (body && body.error) || "error" };
            throw err;
          }, function () {
            throw { _error: "error" };
          });
        })
        .then(function (body) {
          if (requestId !== loadRequestId) return;

          var freshSlots = body.slots || [];

          // Rebuild slot grid from fresh data
          slotGridEl.innerHTML = buildSlotGridHtml(freshSlots);

          // Restore the previously selected slot if it is still open on this day.
          if (prevSlotId) {
            for (var si = 0; si < freshSlots.length; si++) {
              var fs = freshSlots[si];
              if (fs.id === prevSlotId && !fs.full) {
                state.slot = fs.label;
                state.slotId = fs.id;
                window.BKCart.setSlot(fs.label);
                window.BKCart.setSlotId(fs.id);
                break;
              }
            }
          }

          // Update in-memory sold-out state for catalog items on this day
          if (body.categories) {
            body.categories.forEach(function (cat) {
              (cat.dishes || []).forEach(function (d) {
                if (catalogById[d.id]) catalogById[d.id].sold_out = d.sold_out;
              });
            });
            var removed = pruneCartForCategories(body.categories);
            renderLines();
            if (removed.length) {
              var names = removed.length === 1 ? removed[0] : removed.join(", ");
              var verb  = removed.length === 1 ? "isn't" : "aren't";
              var past  = removed.length === 1 ? "was" : "were";
              showDateNotice(names + " " + verb + " available on " + day.long +
                " and " + past + " removed from your basket.");
            }
          }
          renderSlotGrid();
          renderTotalAndContinue();
        })
        .catch(function (err) {
          if (requestId !== loadRequestId) return;
          var code = (err && err._error) || "error";
          if (code === "outside_horizon") {
            slotGridEl.innerHTML = "";
            showDateNotice("That date is no longer in the ordering window — pick another day.");
          } else {
            showDateNotice("Couldn't load " + day.long + "'s slots — try again or pick a different day.");
          }
          renderTotalAndContinue();
        });
    }

    // ---- event delegation: line steppers + edit ----

    linesEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action]");
      if (!btn) return;
      var action  = btn.getAttribute("data-action");
      var lineId  = btn.getAttribute("data-line-id");
      var allLines, found, i;

      if (action === "increment" || action === "decrement") {
        allLines = window.BKCart.getLines();
        found = null;
        for (i = 0; i < allLines.length; i++) {
          if (allLines[i].id === lineId) { found = allLines[i]; break; }
        }
        if (!found) return;
        if (action === "increment") {
          if (found.qty < 20) window.BKCart.updateLine(lineId, { qty: found.qty + 1 });
        } else {
          if (found.qty <= 1) {
            window.BKCart.removeLine(lineId);
          } else {
            window.BKCart.updateLine(lineId, { qty: found.qty - 1 });
          }
        }
        renderLines();
        renderTotalAndContinue();

      } else if (action === "edit") {
        var itemId = parseInt(btn.getAttribute("data-item-id"), 10);
        if (lineId && itemId && window.BKItemSheet) {
          window.BKItemSheet.openEdit(lineId, itemId);
        }
      }
    });

    // ---- event delegation: day chips ----

    dayChipsEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-day-index]");
      if (!btn) return;
      var newIndex = parseInt(btn.getAttribute("data-day-index"), 10);
      if (newIndex === state.dayIndex) return;
      state.dayIndex = newIndex;
      state.dayIso   = days[newIndex] ? days[newIndex].iso : null;
      window.BKCart.setDayIso(state.dayIso);
      renderDayChips();
      loadDay(state.dayIndex);
    });

    // ---- event delegation: slot chips ----

    slotGridEl.addEventListener("click", function (e) {
      var btn = e.target.closest(".bk-slot-chip");
      if (!btn || btn.disabled) return;
      state.slot   = btn.getAttribute("data-slot");
      state.slotId = parseInt(btn.getAttribute("data-slot-id"), 10);
      window.BKCart.setSlot(state.slot);
      window.BKCart.setSlotId(state.slotId);
      renderSlotGrid();
      renderTotalAndContinue();
    });

    // ---- Continue button ----

    if (continueBtn) {
      continueBtn.addEventListener("click", function () {
        if (!continueBtn.disabled)
          window.location.href = continueBtn.getAttribute("data-checkout-url");
      });
    }

    // ---- item sheet callbacks ----

    // Updated (qty/heat/extras changed in edit mode)
    document.addEventListener("bkItemSheet:updated", function () {
      renderLines();
      renderTotalAndContinue();
    });
    // Added (shouldn't happen from basket, but be defensive)
    document.addEventListener("bkItemSheet:added", function () {
      renderLines();
      renderTotalAndContinue();
    });

    // ---- initial render ----

    // If the stored day is not the first orderable day, fetch its slots now.
    // Pass preserveSlot=true: this is an initial load for the already-stored day,
    // so try to restore the previously selected slot if it's still open.
    if (state.dayIndex !== 0) {
      renderAll();
      loadDay(state.dayIndex, true);
    } else {
      renderAll();
    }
  });
})();
