// order.js — Menu screen (PR 5). Sticky filter chips, item sheet overlay,
// and (Monday-sprint Phase 1a) day-chip live refresh.
//
// Day chips: picking a different day fetches GET /api/order/day/<date>/
// and re-renders the dish-list DOM to match that day's availability.
// Any basket lines that are unavailable on the new day are removed with
// an inline notice. Slot state (dayIso / slotLabel / slotId) in the cart
// is also updated so the basket screen starts in sync with the chosen day.
//
// The dish-card and section HTML rendered by JS matches the server-side
// template exactly (see order.html).  No libraries, no HTMX — plain fetch
// + innerHTML, same pattern as checkout.js.
(function () {
  "use strict";

  // ---- utilities ----

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
  }

  // Mirror core.money.format_cents / the `cents` template filter.
  function formatCents(cents) {
    var n = Math.round(Number(cents));
    var sign = n < 0 ? "-" : "";
    var abs = Math.abs(n);
    var whole = Math.floor(abs / 100);
    var sub = abs % 100;
    var grouped = String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return sign + "R " + grouped + "." + (sub < 10 ? "0" : "") + sub;
  }

  function readJSONScript(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try { return JSON.parse(el.textContent); } catch (e) { return fallback; }
  }

  // ---- dish-card HTML renderer (mirrors order.html's dish-row structure) ----

  function buildDishCardHtml(dish) {
    var soldOut = dish.sold_out;
    var hasPhoto = !!dish.photo_url;
    var rowClass = "op-dish-row has-photo" +
      (soldOut ? " is-sold-out" : "") +
      (!hasPhoto ? " is-placeholder" : "");
    var photoEl = hasPhoto
      ? '<img class="op-dish-photo" src="' + escapeHtml(dish.photo_url) + '" alt=""' +
        ' onerror="this.removeAttribute(\'src\'); this.closest(\'.has-photo\')?.classList.add(\'is-placeholder\')">'
      : '<div class="op-dish-photo" aria-hidden="true"></div>';
    var portionEl = dish.portion_label
      ? '<div class="op-dish-note">' + escapeHtml(dish.portion_label) + "</div>"
      : "";
    var qtyEl = soldOut
      ? '<div class="op-dish-qty"><span class="tag tag-neutral">Sold out</span></div>'
      : '<div class="op-dish-qty"><button type="button" class="btn btn-secondary btn-add"' +
        ' data-action="open-sheet" aria-label="Add ' + escapeHtml(dish.name) + '">+</button></div>';

    return '<div class="' + rowClass + '"' +
      ' data-dish-id="' + dish.id + '" data-item-id="' + dish.id + '">' +
      photoEl +
      '<div>' +
      '<div class="op-dish-name">' + escapeHtml(dish.name) + "</div>" +
      '<div class="op-dish-desc">' + escapeHtml(dish.short_description || "") + "</div>" +
      portionEl +
      '<div class="op-dish-price">' + formatCents(dish.price_cents) + "</div>" +
      "</div>" +
      qtyEl +
      "</div>";
  }

  // ---- section HTML renderer (mirrors order.html's op-section structure) ----

  function buildSectionHtml(section, dishesById, isFirst) {
    var dishIds = section.dish_ids || [];
    var cardsHtml = "";
    dishIds.forEach(function (id) {
      var dish = dishesById[id];
      if (dish) cardsHtml += buildDishCardHtml(dish);
    });
    if (!cardsHtml) {
      cardsHtml = '<p class="op-sheet-empty">Nothing in this section this week.</p>';
    }
    return '<div class="op-section" id="section-' + escapeHtml(section.id) + '"' +
      (isFirst ? "" : " hidden") + ">" +
      '<div class="op-cat-head">' +
      '<h3 class="op-cat-name">' + escapeHtml(section.label) + "</h3>" +
      '<span class="op-cat-rule"></span>' +
      "</div>" +
      cardsHtml +
      "</div>";
  }

  // ---- rebuild filter-chip bar to match new sections ----

  function rebuildFilterBar(filterBar, sections, activeChipId) {
    var html = "";
    sections.forEach(function (section) {
      var isActive = section.id === (activeChipId || "all");
      html += '<button type="button" class="op-filter-chip' + (isActive ? " is-selected" : "") + '"' +
        ' data-chip="' + escapeHtml(section.id) + '">' + escapeHtml(section.label) + "</button>";
    });
    filterBar.innerHTML = html;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var menuEl     = document.getElementById("op-menu");
    var filterBar  = document.getElementById("op-filter-bar");
    var dayBarEl   = document.getElementById("op-day-bar");
    var noticeEl   = document.getElementById("op-date-notice");
    var contextEl  = document.getElementById("op-context");

    if (!menuEl) return;

    var days = readJSONScript("op-days-data", []);
    var dayUrlBase = (window.OP_URLS && window.OP_URLS.api_day_base) || "/api/order/day/";

    var state = {
      dayIndex: 0,
      dayIso:   days[0] ? days[0].iso : null,
    };

    var loadRequestId = 0;

    // ---- show / hide notice ----

    function showNotice(msg, isError) {
      if (!noticeEl) return;
      noticeEl.textContent = msg;
      noticeEl.hidden = false;
      noticeEl.classList.toggle("is-error", !!isError);
    }
    function clearNotice() {
      if (!noticeEl) return;
      noticeEl.hidden = true;
      noticeEl.textContent = "";
      noticeEl.classList.remove("is-error");
    }

    // ---- chip section navigation (category filter) ----

    function showChip(id) {
      var known = false;
      menuEl.querySelectorAll(".op-section").forEach(function (sec) {
        if (sec.id === "section-" + id) known = true;
      });
      var activeId = known ? id : "all";
      menuEl.querySelectorAll(".op-section").forEach(function (sec) {
        sec.hidden = sec.id !== "section-" + activeId;
      });
      document.querySelectorAll(".op-filter-chip").forEach(function (chip) {
        chip.classList.toggle("is-selected", chip.getAttribute("data-chip") === activeId);
      });
      var section = document.getElementById("section-" + activeId);
      if (section) section.scrollIntoView({ block: "start" });
    }

    // ---- item sheet (add mode) ----

    menuEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action='open-sheet']");
      var row = e.target.closest(".op-dish-row:not(.is-sold-out)");
      if (!row) return;
      if (btn && btn.disabled) return;
      var itemId = parseInt(row.getAttribute("data-item-id"), 10);
      if (itemId && window.BKItemSheet) window.BKItemSheet.open(itemId);
    });

    // ---- filter bar ----

    if (filterBar) {
      filterBar.addEventListener("click", function (e) {
        var chip = e.target.closest("[data-chip]");
        if (!chip) return;
        var id = chip.getAttribute("data-chip");
        showChip(id);
        if (history.replaceState) history.replaceState(null, "", "#" + id);
      });
    }

    // ---- prune basket lines no longer available on the new day ----

    function pruneCartForDishes(dishes) {
      // Build set of ids that are available (not sold_out) on the new day
      var available = {};
      dishes.forEach(function (d) {
        if (!d.sold_out) available[d.id] = true;
      });
      var removed = [];
      if (!window.BKCart) return removed;
      var lines = window.BKCart.getLines().slice();
      lines.forEach(function (l) {
        if (!available[l.itemId]) {
          removed.push(l.name);
          window.BKCart.removeLine(l.id);
        }
      });
      return removed;
    }

    // ---- day chip handler ----

    function loadDay(dayIndex) {
      var day = days[dayIndex];
      if (!day) return;

      // Immediately clear slot state — the chosen slot belongs to the old day.
      if (window.BKCart) {
        window.BKCart.setSlot(null);
        window.BKCart.setSlotId(null);
        window.BKCart.setDayIso(day.iso);
      }
      clearNotice();

      var requestId = ++loadRequestId;
      var url = dayUrlBase + encodeURIComponent(day.iso) + "/";

      fetch(url, { credentials: "same-origin" })
        .then(function (resp) {
          if (resp.ok) return resp.json();
          return resp.json().then(function (body) {
            throw { _error: (body && body.error) || "error" };
          }, function () {
            throw { _error: "error" };
          });
        })
        .then(function (body) {
          if (requestId !== loadRequestId) return;

          var dishes = body.dishes || [];
          var sections = body.sections || [];

          // Build dishes lookup by id for card rendering
          var dishesById = {};
          dishes.forEach(function (d) { dishesById[d.id] = d; });

          // Rebuild the category filter bar to match the new sections
          if (filterBar) {
            rebuildFilterBar(filterBar, sections, "all");
          }

          // Rebuild the menu sections DOM
          var sectionsHtml = "";
          sections.forEach(function (section, i) {
            sectionsHtml += buildSectionHtml(section, dishesById, i === 0);
          });
          menuEl.innerHTML = sectionsHtml;

          // Update context line (collection day label)
          if (contextEl && day.long) {
            var longLabel = day.long.charAt(0).toUpperCase() + day.long.slice(1);
            contextEl.textContent = "Collection · " + longLabel;
            contextEl.hidden = false;
          }

          // Prune basket lines unavailable on the new day
          var removed = pruneCartForDishes(dishes);
          if (removed.length) {
            showNotice("Some items were removed — not available on this day.");
          }

          // Update item-sheet catalog sold_out state so the sheet reflects
          // the new day's availability if it opens after a day change.
          if (window.BKItemSheet && window.BKItemSheet.updateCatalog) {
            window.BKItemSheet.updateCatalog(dishes);
          }
        })
        .catch(function (err) {
          if (requestId !== loadRequestId) return;
          var code = (err && err._error) || "error";
          if (code === "invalid date") {
            showNotice("That date is no longer available — pick another day.", true);
          } else {
            showNotice("Couldn't load that day's menu — try again.", true);
          }
        });
    }

    // ---- day chip bar interaction ----

    if (dayBarEl) {
      // Mark the first chip selected on initial render (already done by server,
      // but re-apply in case BKCart.getDayIso() differs from index 0).
      var storedIso = window.BKCart ? window.BKCart.getDayIso() : null;
      if (storedIso) {
        var foundIdx = -1;
        for (var di = 0; di < days.length; di++) {
          if (days[di].iso === storedIso) { foundIdx = di; break; }
        }
        if (foundIdx > 0) {
          state.dayIndex = foundIdx;
          state.dayIso = storedIso;
          dayBarEl.querySelectorAll(".op-day-chip").forEach(function (btn) {
            var idx = parseInt(btn.getAttribute("data-day-index"), 10);
            btn.classList.toggle("is-selected", idx === state.dayIndex);
          });
          // Load the stored day's dishes (the page rendered day 0's menu)
          loadDay(state.dayIndex);
        }
      }

      dayBarEl.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-day-index]");
        if (!btn || btn.disabled) return;
        var newIndex = parseInt(btn.getAttribute("data-day-index"), 10);
        if (newIndex === state.dayIndex) return;
        state.dayIndex = newIndex;
        state.dayIso = days[newIndex] ? days[newIndex].iso : null;
        dayBarEl.querySelectorAll(".op-day-chip").forEach(function (chip) {
          var idx = parseInt(chip.getAttribute("data-day-index"), 10);
          chip.classList.toggle("is-selected", idx === state.dayIndex);
        });
        loadDay(state.dayIndex);
      });
    }

    // ---- initial hash navigation ----

    var hash = (location.hash || "").replace(/^#/, "");
    if (hash) showChip(hash);
  });
})();
