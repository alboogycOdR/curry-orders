// order.js — the Order screen (design handoff §"Screens" §2): qty
// steppers on the menu, day/slot pickers, order sheet and total. Menu
// listing is server-rendered for the *first* orderable day only
// (order.html); picking a different day re-fetches and rebuilds it —
// Monday-sprint Phase 1a (docs/MONDAY_SPRINT.md), see order.html's own
// comment on this for why. Builds on the shared cart.js (loaded first).
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
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var days = readJSONScript("days-data", []); // [{index, dow, dom, long, iso}]
    var eftHoldMinutes = readJSONScript("eft-hold-minutes-data", 30); // core.models.Settings.eft_hold_minutes

    var menuEl = document.getElementById("op-menu");
    var dayChipsEl = document.getElementById("op-day-chips");
    var slotGridEl = document.getElementById("op-slot-grid");
    var slotNoteEl = document.getElementById("op-slot-note");
    var dateNoticeEl = document.getElementById("op-date-notice");
    var sheetEl = document.getElementById("op-sheet");
    var totalEl = document.getElementById("op-total-value");
    var continueBtn = document.getElementById("op-continue");
    var readyHintEl = document.getElementById("op-ready-hint");

    var state = {
      day: clampDay(window.BKCart.getDay()),
      slot: window.BKCart.getSlot(),
      slotId: window.BKCart.getSlotId(),
    };
    // Guards against an out-of-order response: if the customer taps two
    // day chips in quick succession, only the most recent request's
    // result is allowed to land.
    var loadRequestId = 0;

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
      var control = row.querySelector("[data-qty-control]");
      // A sold-out row has no qty control at all (order.html/
      // buildMenuHtml renders a static "Sold out" tag instead) --
      // nothing to wire up. Previously unguarded: this threw on the
      // first sold-out dish encountered and silently killed every
      // renderAll() call after it in the same page load (day switching,
      // slot picking, add-to-cart, totals -- all of it), independently
      // found while rewriting this function for Phase 1a.
      if (!control) return;

      var id = row.getAttribute("data-dish-id");
      var name = row.getAttribute("data-dish-name");
      var price = parseFloat(row.getAttribute("data-dish-price"));
      var qty = dishRowQty(id);
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
      // Full/disabled state comes from the day's own data (server-
      // rendered for the first day, from GET /api/availability for any
      // other — see loadDay()) — this only ever manages which chip
      // looks selected, never which ones are clickable.
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
      var totalRow = document.getElementById("op-total-row");
      if (totalRow) totalRow.classList.toggle("is-empty", t.count === 0);
      if (t.count === 0) {
        totalEl.textContent = "";
      } else {
        totalEl.textContent = window.BKCart.rands(t.total);
      }
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

    function showDateNotice(message, isError) {
      dateNoticeEl.textContent = message;
      dateNoticeEl.classList.toggle("is-error", !!isError);
      dateNoticeEl.hidden = false;
    }

    function clearDateNotice() {
      dateNoticeEl.hidden = true;
      dateNoticeEl.textContent = "";
      dateNoticeEl.classList.remove("is-error");
    }

    var CHIP_TILES = [
      { id: "roti", label: "Roti", cats: ["Masala Roti Rolls", "Roti & Curry", "Roti & Gatsby, Large"] },
      { id: "gatsby", label: "Gatsby", cats: ["Gatsby", "Roti & Gatsby, Large"] },
      { id: "curry", label: "Curry", cats: ["Roti & Curry"] },
      { id: "lasagne", label: "Lasagne", cats: ["Italian Lasagne"] },
    ];
    var THIS_WEEK_SLUGS = [
      "chicken-masala-roti-roll",
      "full-house-masala-steak-gatsby",
      "beef-lasagne",
    ];

    function flattenDishes(categories) {
      var dishes = [];
      var seen = {};
      categories.forEach(function (cat) {
        (cat.dishes || []).forEach(function (dish) {
          if (seen[dish.id]) return;
          seen[dish.id] = true;
          dishes.push({
            id: dish.id,
            slug: dish.slug || "",
            name: dish.name,
            short_description: dish.short_description || "",
            price_cents: dish.price_cents,
            sold_out: !!dish.sold_out,
            photo_url: dish.photo_url || "",
            portion_label: dish.portion_label || cat.portion_label || "",
            category: dish.category || cat.name || "",
          });
        });
      });
      return dishes;
    }

    function uniqueById(list) {
      var seen = {};
      var out = [];
      list.forEach(function (d) {
        if (seen[d.id]) return;
        seen[d.id] = true;
        out.push(d);
      });
      return out;
    }

    function dishRowHtml(dish) {
      var photo = dish.photo_url
        ? '<img class="op-dish-photo" src="' + escapeHtml(dish.photo_url) + '" alt="" ' +
          "onerror=\"this.removeAttribute('src'); this.closest('.has-photo')?.classList.add('is-placeholder')\">"
        : '<div class="op-dish-photo" aria-hidden="true"></div>';
      var qty = dish.sold_out
        ? '<div class="op-dish-qty"><span class="tag tag-neutral">Sold out</span></div>'
        : '<div class="op-dish-qty" data-qty-control></div>';
      return (
        '<div class="op-dish-row has-photo' +
        (dish.sold_out ? " is-sold-out" : "") +
        (dish.photo_url ? "" : " is-placeholder") +
        '" data-dish-id="' + dish.id + '" data-dish-name="' + escapeHtml(dish.name) +
        '" data-dish-price="' + dish.price_cents + '">' +
        photo +
        "<div><div class=\"op-dish-name\">" + escapeHtml(dish.name) + "</div>" +
        '<div class="op-dish-desc">' + escapeHtml(dish.short_description) + "</div>" +
        (dish.portion_label ? '<div class="op-dish-note">' + escapeHtml(dish.portion_label) + "</div>" : "") +
        '<div class="op-dish-price">' + window.BKCart.rands(dish.price_cents) + "</div></div>" +
        qty +
        "</div>"
      );
    }

    function sectionHtml(id, label, dishes) {
      var rows = dishes.length
        ? dishes.map(dishRowHtml).join("")
        : '<p class="op-sheet-empty">Nothing in this section this week.</p>';
      return (
        '<div class="op-section" id="section-' + id + '"' +
        (id === "all" ? "" : " hidden") +
        '><div class="op-cat-head"><h3 class="op-cat-name">' + escapeHtml(label) +
        '</h3><span class="op-cat-rule"></span></div>' + rows + "</div>"
      );
    }

    function buildMenuHtml(categories) {
      var dishes = flattenDishes(categories);
      var bySlug = {};
      dishes.forEach(function (d) { if (d.slug) bySlug[d.slug] = d; });
      var featured = (new URLSearchParams(location.search).get("featured") || "");
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
      var html = "";
      slots.forEach(function (s) {
        html +=
          '<button type="button" class="op-chip op-slot-chip' + (s.full ? " is-full" : "") + '" ' +
          'data-slot-id="' + s.id + '" data-slot="' + escapeHtml(s.label) + '"' +
          (s.full ? " disabled" : "") + ">" + escapeHtml(s.label) + "</button>";
      });
      return html;
    }

    // Removes any basket line for a dish that's either sold out on the
    // newly chosen date or no longer in the active menu at all. Never a
    // silent drop — returns the removed names so the caller can tell
    // the customer plainly what happened and why.
    function pruneCartForCategories(categories) {
      var availableIds = {};
      categories.forEach(function (cat) {
        cat.dishes.forEach(function (dish) {
          if (!dish.sold_out) availableIds[dish.id] = true;
        });
      });
      var cart = window.BKCart.getCart();
      var removedNames = [];
      var changed = false;
      Object.keys(cart).forEach(function (key) {
        var dishId = parseInt(String(key).split(":")[0], 10);
        if (!availableIds[dishId]) {
          removedNames.push(cart[key].name);
          delete cart[key];
          changed = true;
        }
      });
      if (changed) window.BKCart.setCart(cart);
      return removedNames;
    }

    function loadDay(dayIndex) {
      var day = days[dayIndex];
      if (!day) return;

      // Cleared immediately, before the fetch even starts -- a slot
      // that belonged to the previous day must never survive into this
      // one, even if the fetch is slow or fails outright. This is the
      // core of the bug this whole function exists to fix.
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
          if (requestId !== loadRequestId) return; // superseded by a later click
          menuEl.innerHTML = buildMenuHtml(body.categories);
          slotGridEl.innerHTML = buildSlotGridHtml(body.slots);
          var removed = pruneCartForCategories(body.categories);
          renderMenu();
          renderSlotGrid();
          renderSheet();
          renderTotalsAndCta();
          var hash = (location.hash || "").replace(/^#/, "");
          if (hash) showChip(hash);
          if (removed.length) {
            var subject = removed.length === 1 ? removed[0] : removed.join(", ");
            var verb = removed.length === 1 ? "isn't" : "aren't";
            var pastVerb = removed.length === 1 ? "was" : "were";
            showDateNotice(
              subject + " " + verb + " available on " + day.long + " and " + pastVerb +
                " removed from your order.",
              false
            );
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
      var newDay = parseInt(btn.getAttribute("data-day-index"), 10);
      if (newDay === state.day) return;
      state.day = newDay;
      window.BKCart.setDay(state.day);
      renderDayChips();
      loadDay(state.day);
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

    function showChip(id) {
      var known = false;
      menuEl.querySelectorAll(".op-section").forEach(function (sec) {
        var match = sec.id === "section-" + id;
        if (match) known = true;
        sec.hidden = !match;
      });
      if (!known) {
        id = "all";
        menuEl.querySelectorAll(".op-section").forEach(function (sec) {
          sec.hidden = sec.id !== "section-all";
        });
      }
      document.querySelectorAll(".op-filter-chip").forEach(function (chip) {
        chip.classList.toggle("is-selected", chip.getAttribute("data-chip") === id);
      });
      var section = document.getElementById("section-" + id);
      if (section) section.scrollIntoView({ block: "start" });
    }

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

    // The page is always server-rendered for days[0] (public/views.py's
    // order() only ever renders the first orderable day) -- if a
    // returning visitor's stored day is anything else, that markup is
    // already wrong for their actual selection the instant the page
    // loads, the exact same bug loadDay() fixes for an in-page switch.
    // Fetch it properly rather than trust stale server HTML.
    if (state.day !== 0) {
      renderDayChips();
      loadDay(state.day);
    } else {
      renderAll();
      var hash = (location.hash || "").replace(/^#/, "");
      if (hash) showChip(hash);
    }
  });
})();
