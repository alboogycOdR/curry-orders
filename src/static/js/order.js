// order.js — the Menu screen (PR 4). Sticky chips, photo cards, item
// sheet overlay. Day/slot picker stays on this screen through PR 4;
// PR 5 moves them to /basket/.
//
// Cart v2 API: getDayIso()/setDayIso() (never getDay()/setDay()).
// Item clicks open BKItemSheet; the old bump() no longer exists here.
// Builds on cart.js (loaded first) and item-sheet.js (loaded after).
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

  document.addEventListener("DOMContentLoaded", function () {
    var days = readJSONScript("days-data", []); // [{index, dow, dom, long, iso}]
    var eftHoldMinutes = readJSONScript("eft-hold-minutes-data", 30);

    var menuEl        = document.getElementById("op-menu");
    var dayChipsEl    = document.getElementById("op-day-chips");
    var slotGridEl    = document.getElementById("op-slot-grid");
    var slotNoteEl    = document.getElementById("op-slot-note");
    var dateNoticeEl  = document.getElementById("op-date-notice");
    var sheetEl       = document.getElementById("op-sheet");
    var totalEl       = document.getElementById("op-total-value");
    var continueBtn   = document.getElementById("op-continue");
    var readyHintEl   = document.getElementById("op-ready-hint");

    // Resolve the stored dayIso to an index in the days list (or 0).
    var storedDayIso = window.BKCart.getDayIso();
    var initialDayIndex = 0;
    if (storedDayIso) {
      for (var di = 0; di < days.length; di++) {
        if (days[di].iso === storedDayIso) { initialDayIndex = di; break; }
      }
    }

    var state = {
      dayIndex: initialDayIndex,
      dayIso:   storedDayIso || (days[0] ? days[0].iso : null),
      slot:     window.BKCart.getSlot(),
      slotId:   window.BKCart.getSlotId(),
    };

    var loadRequestId = 0;

    // ---- slot helpers ----

    function renderDayChips() {
      dayChipsEl.querySelectorAll("[data-day-index]").forEach(function (btn) {
        var idx = parseInt(btn.getAttribute("data-day-index"), 10);
        btn.classList.toggle("is-selected", idx === state.dayIndex);
      });
    }

    function renderSlotGrid() {
      slotGridEl.querySelectorAll(".op-slot-chip").forEach(function (btn) {
        var slotId = parseInt(btn.getAttribute("data-slot-id"), 10);
        btn.classList.toggle("is-selected", !btn.disabled && slotId === state.slotId);
      });
      slotNoteEl.textContent = state.slot
        ? "Held for " + eftHoldMinutes + " minutes once you place the order."
        : "Pick a collection window — some may already be full for today.";
    }

    // ---- totals / CTA ----

    function renderTotalsAndCta() {
      var t = window.BKCart.totals();
      var totalRow = document.getElementById("op-total-row");
      if (totalRow) totalRow.classList.toggle("is-empty", t.count === 0);
      totalEl.textContent = t.count > 0 ? window.BKCart.rands(t.total) : "";
      var ready = t.count > 0 && !!state.slot;
      continueBtn.disabled = !ready;
      if (ready) {
        var day = days[state.dayIndex];
        readyHintEl.textContent = "Slot " + state.slot + ", " + (day ? day.long : "") + ".";
      } else {
        readyHintEl.textContent = "Pick at least one dish and a collection window.";
      }
    }

    // ---- cart-sheet sidebar (panel on desktop) ----

    function renderSheet() {
      var lines = window.BKCart.getLines();
      if (!lines.length) {
        sheetEl.innerHTML =
          '<p class="op-sheet-empty">Nothing on the sheet yet. Add a dish and it lands here.</p>';
        return;
      }
      var html = "";
      lines.forEach(function (l) {
        html +=
          '<div class="op-sheet-line">' +
          '<span class="op-sheet-qty">' + l.qty + "&times;</span>" +
          '<span class="op-sheet-name">' + escapeHtml(l.name) +
          (l.heat ? " <span style=\"font-size:12px;opacity:.7;\">" + escapeHtml(l.heat) + "</span>" : "") +
          "</span>" +
          '<span class="op-sheet-total">' + window.BKCart.rands(l.qty * l.unitPrice) + "</span>" +
          "</div>";
      });
      sheetEl.innerHTML = html;
    }

    function renderAll() {
      renderDayChips();
      renderSlotGrid();
      renderSheet();
      renderTotalsAndCta();
    }

    // ---- date notice ----

    function showDateNotice(msg, isError) {
      dateNoticeEl.textContent = msg;
      dateNoticeEl.classList.toggle("is-error", !!isError);
      dateNoticeEl.hidden = false;
    }
    function clearDateNotice() {
      dateNoticeEl.hidden = true;
      dateNoticeEl.textContent = "";
      dateNoticeEl.classList.remove("is-error");
    }

    // ---- chip/section helpers ----

    var CHIP_TILES = [
      { id: "roti",    label: "Roti",    cats: ["Masala Roti Rolls", "Roti & Curry", "Roti & Gatsby, Large"] },
      { id: "gatsby",  label: "Gatsby",  cats: ["Gatsby", "Roti & Gatsby, Large"] },
      { id: "curry",   label: "Curry",   cats: ["Roti & Curry"] },
      { id: "lasagne", label: "Lasagne", cats: ["Italian Lasagne"] },
    ];
    var THIS_WEEK_SLUGS = [
      "chicken-masala-roti-roll",
      "full-house-masala-steak-gatsby",
      "beef-lasagne",
    ];

    function flattenDishes(categories) {
      var dishes = [], seen = {};
      categories.forEach(function (cat) {
        (cat.dishes || []).forEach(function (dish) {
          if (seen[dish.id]) return;
          seen[dish.id] = true;
          dishes.push({
            id: dish.id, slug: dish.slug || "", name: dish.name,
            short_description: dish.short_description || "",
            price_cents: dish.price_cents, sold_out: !!dish.sold_out,
            photo_url: dish.photo_url || "",
            portion_label: dish.portion_label || cat.portion_label || "",
            category: dish.category || cat.name || "",
          });
        });
      });
      return dishes;
    }

    function uniqueById(list) {
      var seen = {}, out = [];
      list.forEach(function (d) { if (!seen[d.id]) { seen[d.id] = true; out.push(d); } });
      return out;
    }

    function dishRowHtml(dish) {
      var photo = dish.photo_url
        ? '<img class="op-dish-photo" src="' + escapeHtml(dish.photo_url) + '" alt="" ' +
          "onerror=\"this.removeAttribute('src'); this.closest('.has-photo')?.classList.add('is-placeholder')\">"
        : '<div class="op-dish-photo" aria-hidden="true"></div>';
      var qty = dish.sold_out
        ? '<div class="op-dish-qty"><span class="tag tag-neutral">Sold out</span></div>'
        : '<div class="op-dish-qty"><button type="button" class="btn btn-secondary btn-add" ' +
          'data-action="open-sheet" aria-label="Add ' + escapeHtml(dish.name) + '">+</button></div>';
      return (
        '<div class="op-dish-row has-photo' +
        (dish.sold_out ? " is-sold-out" : "") +
        (dish.photo_url ? "" : " is-placeholder") +
        '" data-dish-id="' + dish.id + '" data-item-id="' + dish.id + '">' +
        photo +
        "<div><div class=\"op-dish-name\">" + escapeHtml(dish.name) + "</div>" +
        '<div class="op-dish-desc">' + escapeHtml(dish.short_description) + "</div>" +
        (dish.portion_label ? '<div class="op-dish-note">' + escapeHtml(dish.portion_label) + "</div>" : "") +
        '<div class="op-dish-price">' + window.BKCart.rands(dish.price_cents) + "</div></div>" +
        qty + "</div>"
      );
    }

    function sectionHtml(id, label, dishes) {
      var rows = dishes.length
        ? dishes.map(dishRowHtml).join("")
        : '<p class="op-sheet-empty">Nothing in this section this week.</p>';
      return (
        '<div class="op-section" id="section-' + id + '"' +
        (id === "all" ? "" : " hidden") + '>' +
        '<div class="op-cat-head"><h3 class="op-cat-name">' + escapeHtml(label) +
        '</h3><span class="op-cat-rule"></span></div>' + rows + "</div>"
      );
    }

    function buildMenuHtml(categories) {
      var dishes = flattenDishes(categories);
      var bySlug = {};
      dishes.forEach(function (d) { if (d.slug) bySlug[d.slug] = d; });
      var featured = new URLSearchParams(location.search).get("featured") || "";
      var thisWeek = [];
      [featured].concat(THIS_WEEK_SLUGS).forEach(function (slug) {
        if (slug && bySlug[slug]) thisWeek.push(bySlug[slug]);
      });
      thisWeek = uniqueById(thisWeek);
      var html = sectionHtml("all", "All", uniqueById(dishes));
      html += sectionHtml("this-week", "This week", thisWeek);
      CHIP_TILES.forEach(function (chip) {
        var members = dishes.filter(function (d) { return chip.cats.indexOf(d.category) !== -1; });
        html += sectionHtml(chip.id, chip.label, members);
      });
      return html;
    }

    function buildSlotGridHtml(slots) {
      return slots.map(function (s) {
        return '<button type="button" class="op-chip op-slot-chip' + (s.full ? " is-full" : "") +
          '" data-slot-id="' + s.id + '" data-slot="' + escapeHtml(s.label) + '"' +
          (s.full ? " disabled" : "") + ">" + escapeHtml(s.label) + "</button>";
      }).join("");
    }

    // Remove basket lines for dishes not available on the new day
    function pruneCartForCategories(categories) {
      var available = {};
      categories.forEach(function (cat) {
        cat.dishes.forEach(function (dish) { if (!dish.sold_out) available[dish.id] = true; });
      });
      var removed = [];
      var lines = window.BKCart.getLines().slice();
      lines.forEach(function (l) {
        if (!available[l.itemId]) {
          removed.push(l.name);
          window.BKCart.removeLine(l.id);
        }
      });
      return removed;
    }

    function showChip(id) {
      var known = false;
      menuEl.querySelectorAll(".op-section").forEach(function (sec) {
        var match = sec.id === "section-" + id;
        if (match) known = true;
        sec.hidden = !match;
      });
      if (!known) id = "all";
      menuEl.querySelectorAll(".op-section").forEach(function (sec) {
        if (!known) sec.hidden = sec.id !== "section-all";
      });
      document.querySelectorAll(".op-filter-chip").forEach(function (chip) {
        chip.classList.toggle("is-selected", chip.getAttribute("data-chip") === id);
      });
      var section = document.getElementById("section-" + id);
      if (section) section.scrollIntoView({ block: "start" });
    }

    // ---- day load (fetch) ----

    function loadDay(dayIndex) {
      var day = days[dayIndex];
      if (!day) return;
      // Clear slot immediately
      state.slot = null;
      state.slotId = null;
      window.BKCart.setSlot(null);
      window.BKCart.setSlotId(null);
      clearDateNotice();
      renderSlotGrid();
      renderTotalsAndCta();

      var requestId = ++loadRequestId;
      menuEl.setAttribute("aria-busy", "true");
      var url = window.BK_ORDER_URLS.api_availability + "?date=" + encodeURIComponent(day.iso);
      fetch(url, { credentials: "same-origin" })
        .then(function (resp) {
          if (!resp.ok) throw new Error("bad status " + resp.status);
          return resp.json();
        })
        .then(function (body) {
          if (requestId !== loadRequestId) return;
          menuEl.innerHTML = buildMenuHtml(body.categories);
          slotGridEl.innerHTML = buildSlotGridHtml(body.slots);
          var removed = pruneCartForCategories(body.categories);
          renderSlotGrid();
          renderSheet();
          renderTotalsAndCta();
          var hash = (location.hash || "").replace(/^#/, "");
          if (hash) showChip(hash);
          if (removed.length) {
            var subj = removed.length === 1 ? removed[0] : removed.join(", ");
            var verb = removed.length === 1 ? "isn't" : "aren't";
            var past = removed.length === 1 ? "was" : "were";
            showDateNotice(subj + " " + verb + " available on " + day.long + " and " + past +
              " removed from your order.", false);
          }
        })
        .catch(function () {
          if (requestId !== loadRequestId) return;
          showDateNotice(
            "Couldn't load " + day.long + "'s menu — try again or pick a different day.",
            true
          );
        })
        .then(function () {
          if (requestId === loadRequestId) menuEl.removeAttribute("aria-busy");
        });
    }

    // ---- event delegation ----

    // Open item sheet when a card row (not sold-out) or its + button is clicked
    menuEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action='open-sheet']");
      var row = e.target.closest(".op-dish-row:not(.is-sold-out)");
      if (!row) return;
      // Ignore clicks on disabled + buttons that somehow bubbled
      if (btn && btn.disabled) return;
      var itemId = parseInt(row.getAttribute("data-item-id"), 10);
      if (itemId && window.BKItemSheet) window.BKItemSheet.open(itemId);
    });

    dayChipsEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-day-index]");
      if (!btn) return;
      var newIndex = parseInt(btn.getAttribute("data-day-index"), 10);
      if (newIndex === state.dayIndex) return;
      state.dayIndex = newIndex;
      state.dayIso = days[newIndex] ? days[newIndex].iso : null;
      window.BKCart.setDayIso(state.dayIso);
      renderDayChips();
      loadDay(state.dayIndex);
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
      if (!continueBtn.disabled)
        window.location.href = continueBtn.getAttribute("data-checkout-url");
    });

    var filterBar = document.getElementById("op-filter-bar");
    if (filterBar) {
      filterBar.addEventListener("click", function (e) {
        var chip = e.target.closest("[data-chip]");
        if (!chip) return;
        var id = chip.getAttribute("data-chip");
        showChip(id);
        if (history.replaceState) history.replaceState(null, "", "#" + id);
      });
    }

    // Re-render sheet/totals when item sheet closes with an add/update
    document.addEventListener("bkItemSheet:added", function () {
      renderSheet();
      renderTotalsAndCta();
    });
    document.addEventListener("bkItemSheet:updated", function () {
      renderSheet();
      renderTotalsAndCta();
    });

    // ---- initial render ----
    if (state.dayIndex !== 0) {
      renderDayChips();
      loadDay(state.dayIndex);
    } else {
      renderAll();
      var hash = (location.hash || "").replace(/^#/, "");
      if (hash) showChip(hash);
    }
  });
})();
