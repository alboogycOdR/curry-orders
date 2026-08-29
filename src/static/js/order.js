// order.js — the Order screen (design handoff §"Screens" §2): qty
// steppers on the menu, day/slot pickers, order sheet and total. Menu
// listing itself is server-rendered (order.html); this only drives the
// interactive parts, reading/writing state through window.BKCart
// (cart.js, loaded first — see that file's header).
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

  document.addEventListener("DOMContentLoaded", function () {
    // Dish name/price come off each .op-dish-row's data-* attributes
    // (server-rendered from real core.Dish rows) — no separate menu
    // price map needed here.
    var days = readJSONScript("days-data", []); // [{index, dow, dom, long, ...}]
    var eftHoldMinutes = readJSONScript("eft-hold-minutes-data", 30); // core.models.Settings.eft_hold_minutes

    var menuEl = document.getElementById("op-menu");
    var dayChipsEl = document.getElementById("op-day-chips");
    var slotGridEl = document.getElementById("op-slot-grid");
    var slotNoteEl = document.getElementById("op-slot-note");
    var sheetEl = document.getElementById("op-sheet");
    var totalEl = document.getElementById("op-total-value");
    var continueBtn = document.getElementById("op-continue");
    var readyHintEl = document.getElementById("op-ready-hint");

    var state = {
      day: clampDay(window.BKCart.getDay()),
      slot: window.BKCart.getSlot(),
      slotId: window.BKCart.getSlotId(),
    };

    function clampDay(i) {
      if (!days.length) return 0;
      if (typeof i !== "number" || isNaN(i) || i < 0 || i >= days.length) return 0;
      return i;
    }

    function dishRowQty(id) {
      var cart = window.BKCart.getCart();
      return cart[id] ? cart[id].qty : 0;
    }

    function renderDishRow(row) {
      var id = row.getAttribute("data-dish-id");
      var name = row.getAttribute("data-dish-name");
      var price = parseFloat(row.getAttribute("data-dish-price"));
      var qty = dishRowQty(id);
      var control = row.querySelector("[data-qty-control]");
      if (qty > 0) {
        control.innerHTML =
          '<button type="button" class="btn btn-secondary btn-icon" data-action="dec" aria-label="One fewer">&minus;</button>' +
          '<span class="qty-count">' + qty + "</span>" +
          '<button type="button" class="btn btn-primary btn-icon" data-action="inc" aria-label="One more">+</button>';
      } else {
        control.innerHTML =
          '<button type="button" class="btn btn-secondary btn-add" data-action="add">Add</button>';
      }
      control.dataset.dishId = id;
      control.dataset.dishName = name;
      control.dataset.dishPrice = price;
    }

    function renderMenu() {
      menuEl.querySelectorAll(".op-dish-row").forEach(renderDishRow);
    }

    function renderDayChips() {
      dayChipsEl.querySelectorAll("[data-day-index]").forEach(function (btn) {
        var idx = parseInt(btn.getAttribute("data-day-index"), 10);
        btn.classList.toggle("is-selected", idx === state.day);
      });
    }

    function renderSlotGrid() {
      // Full/disabled state is server-rendered (order.html sets
      // .is-full/disabled per slot from a real occupying-orders count —
      // public.views._slot_list_for_day) — this only ever manages which
      // chip looks selected, never which ones are clickable.
      slotGridEl.querySelectorAll(".op-slot-chip").forEach(function (btn) {
        var slotId = parseInt(btn.getAttribute("data-slot-id"), 10);
        btn.classList.toggle("is-selected", !btn.disabled && slotId === state.slotId);
      });
      slotNoteEl.textContent = state.slot
        ? "Held for " + eftHoldMinutes + " minutes once you place the order."
        : "Pick a collection window — some may already be full for today.";
    }

    function renderSheet() {
      var cart = window.BKCart.getCart();
      var ids = Object.keys(cart);
      if (ids.length === 0) {
        sheetEl.innerHTML =
          '<p class="op-sheet-empty">Nothing on the sheet yet. Add a dish from the menu and it lands here.</p>';
        return;
      }
      var html = "";
      ids.forEach(function (id) {
        var line = cart[id];
        html +=
          '<div class="op-sheet-line">' +
          '<span class="op-sheet-qty">' + line.qty + "&times;</span>" +
          '<span class="op-sheet-name">' + escapeHtml(line.name) + "</span>" +
          '<span class="op-sheet-total">' + window.BKCart.rands(line.qty * line.price) + "</span>" +
          "</div>";
      });
      sheetEl.innerHTML = html;
    }

    function renderTotalsAndCta() {
      var t = window.BKCart.totals();
      totalEl.textContent = window.BKCart.rands(t.total);
      var ready = t.count > 0 && !!state.slot;
      continueBtn.disabled = !ready;
      if (ready) {
        var day = days[state.day];
        var longLabel = day ? day.long : "";
        readyHintEl.textContent = "Slot " + state.slot + ", " + longLabel + ".";
      } else {
        readyHintEl.textContent = "Pick at least one dish and a collection window.";
      }
    }

    function escapeHtml(s) {
      var div = document.createElement("div");
      div.textContent = s;
      return div.innerHTML;
    }

    function renderAll() {
      renderMenu();
      renderDayChips();
      renderSlotGrid();
      renderSheet();
      renderTotalsAndCta();
    }

    menuEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action]");
      if (!btn) return;
      var control = btn.closest("[data-qty-control]");
      var id = control.dataset.dishId;
      var name = control.dataset.dishName;
      var price = parseFloat(control.dataset.dishPrice);
      var delta = btn.getAttribute("data-action") === "dec" ? -1 : 1;
      window.BKCart.bump(id, name, price, delta);
      var row = control.closest(".op-dish-row");
      renderDishRow(row);
      renderSheet();
      renderTotalsAndCta();
    });

    dayChipsEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-day-index]");
      if (!btn) return;
      state.day = parseInt(btn.getAttribute("data-day-index"), 10);
      window.BKCart.setDay(state.day);
      renderDayChips();
      renderSlotGrid();
      renderTotalsAndCta();
    });

    slotGridEl.addEventListener("click", function (e) {
      var btn = e.target.closest(".op-slot-chip");
      if (!btn || btn.disabled) return;
      state.slot = btn.getAttribute("data-slot");
      state.slotId = parseInt(btn.getAttribute("data-slot-id"), 10);
      window.BKCart.setSlot(state.slot);
      window.BKCart.setSlotId(state.slotId);
      renderSlotGrid();
      renderTotalsAndCta();
    });

    continueBtn.addEventListener("click", function () {
      if (continueBtn.disabled) return;
      window.location.href = continueBtn.getAttribute("data-checkout-url");
    });

    renderAll();
  });
})();
