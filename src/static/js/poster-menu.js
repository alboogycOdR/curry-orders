// poster-menu.js — day-chip browsing for the poster Menu page, matching
// the Broadsheet /order/ screen's own day bar (order.js). Not that
// script reused verbatim: order.js's rebuild functions emit Broadsheet's
// `.op-*` markup, which would fight this page's `.pv-card` styling on
// every day switch. Same GET /api/order/day/<date>/ endpoint, same
// category-grouping approach (by dish.category, first-appearance order
// — mirrors core.menu.categories_ordered(), the query views_v2.menu
// itself uses for the initial server render), just emitting `.pv-card`
// markup instead.
//
// No slot picking here — Basket owns that (see menu.html's own
// comment). This only ever clears/updates BKCart's day/slot state the
// same way order.js's loadDay() does: the old slot belongs to the old
// day the moment you switch.
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
    var dayBarEl = document.getElementById("pv-day-bar");
    var filtersEl = document.getElementById("pv-filters");
    var cardsEl = document.getElementById("pv-menu-cards");
    var noticeEl = document.getElementById("pv-day-notice");
    if (!dayBarEl || !cardsEl) return; // not on the Menu page, or menu is closed today

    var days = readJSONScript("pv-days-data", []);
    var dayUrlBase = (window.PV_MENU_URLS && window.PV_MENU_URLS.api_day_base) || "/api/order/day/";
    var featuredSlug = window.PV_FEATURED_SLUG || "";

    var state = { dayIndex: 0, dayIso: days[0] ? days[0].iso : null };
    var loadRequestId = 0;

    function showNotice(msg) {
      if (!noticeEl) return;
      noticeEl.textContent = msg;
      noticeEl.hidden = false;
    }
    function clearNotice() {
      if (!noticeEl) return;
      noticeEl.hidden = true;
      noticeEl.textContent = "";
    }

    function slugify(s) {
      return String(s).toLowerCase().trim()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
    }

    // ---- group dishes by category, first-appearance order (mirrors
    // core.menu.categories_ordered — the same grouping the initial
    // server render used) ----
    function groupByCategory(dishes) {
      var order = [];
      var byCat = {};
      dishes.forEach(function (d) {
        var cat = d.category || "";
        if (!byCat[cat]) { byCat[cat] = []; order.push(cat); }
        byCat[cat].push(d);
      });
      return order.map(function (cat) { return { name: cat, dishes: byCat[cat] }; });
    }

    function buildCardHtml(dish, catName) {
      var isFeatured = featuredSlug && dish.slug === featuredSlug;
      var isOut = !!dish.sold_out;
      var cardClass = "pv-card" + (isFeatured ? " is-featured" : "") + (isOut ? " is-out" : "");
      var imgClass = "pv-card-img" + (dish.photo_url ? "" : " is-placeholder");
      var imgStyle = dish.photo_url ? ' style="background-image:url(\'' + escapeHtml(dish.photo_url) + '\')"' : "";
      var priceHtml = window.BKCart ? window.BKCart.rands(dish.price_cents) : dish.price_cents;
      var actionHtml = isOut
        ? '<span class="pv-out-tag">Sold out</span>'
        : '<button type="button" class="pv-add" data-dish-id="' + dish.id + '" aria-label="Add ' + escapeHtml(dish.name) + '">+</button>';
      return (
        '<article class="' + cardClass + '" data-category="' + escapeHtml(slugify(catName)) + '">' +
        '<div class="' + imgClass + '"' + imgStyle + '>' +
        (isFeatured ? '<span class="pv-tag">This week</span>' : "") +
        "</div>" +
        '<div class="pv-card-body">' +
        '<div class="pv-card-cat">' + escapeHtml(catName) + "</div>" +
        '<h3 class="pv-card-name">' + escapeHtml(dish.name) + "</h3>" +
        '<p class="pv-card-desc">' + escapeHtml(dish.short_description || "") + "</p>" +
        '<div class="pv-card-foot">' +
        '<span class="pv-card-price">' + priceHtml + "</span>" +
        actionHtml +
        "</div>" +
        "</div>" +
        "</article>"
      );
    }

    function rebuildFilters(categories, activeFilter) {
      if (!filtersEl) return;
      var html = '<button type="button" class="pv-filter' + (activeFilter === "all" ? " is-on" : "") +
        '" data-filter="all" role="tab" aria-selected="' + (activeFilter === "all" ? "true" : "false") + '">Everything</button>';
      categories.forEach(function (cat) {
        var slug = slugify(cat.name);
        var isOn = activeFilter === slug;
        html += '<button type="button" class="pv-filter' + (isOn ? " is-on" : "") +
          '" data-filter="' + escapeHtml(slug) + '" role="tab" aria-selected="' + (isOn ? "true" : "false") + '">' +
          escapeHtml(cat.name) + "</button>";
      });
      filtersEl.innerHTML = html;
    }

    function rebuildCards(categories) {
      var html = "";
      categories.forEach(function (cat) {
        cat.dishes.forEach(function (dish) { html += buildCardHtml(dish, cat.name); });
      });
      cardsEl.innerHTML = html || '<p class="pv-sub" style="margin-top:16px;">Nothing on the menu this week.</p>';
    }

    function pruneCartForDishes(dishes) {
      if (!window.BKCart) return [];
      var available = {};
      dishes.forEach(function (d) { if (!d.sold_out) available[d.id] = true; });
      var removed = [];
      window.BKCart.getLines().slice().forEach(function (l) {
        if (!available[l.itemId]) {
          removed.push(l.name);
          window.BKCart.removeLine(l.id);
        }
      });
      return removed;
    }

    function loadDay(dayIndex) {
      var day = days[dayIndex];
      if (!day) return;

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
          }, function () { throw { _error: "error" }; });
        })
        .then(function (body) {
          if (requestId !== loadRequestId) return;
          var dishes = body.dishes || [];
          var categories = groupByCategory(dishes);
          rebuildFilters(categories, "all");
          rebuildCards(categories);
          var removed = pruneCartForDishes(dishes);
          if (removed.length) {
            showNotice("Some items were removed — not available on this day.");
          }
        })
        .catch(function (err) {
          if (requestId !== loadRequestId) return;
          var code = (err && err._error) || "error";
          showNotice(
            code === "invalid date"
              ? "That date is no longer available — pick another day."
              : "Couldn't load that day's menu — try again."
          );
        });
    }

    dayBarEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-day-index]");
      if (!btn || btn.disabled) return;
      var newIndex = parseInt(btn.getAttribute("data-day-index"), 10);
      if (newIndex === state.dayIndex) return;
      state.dayIndex = newIndex;
      state.dayIso = days[newIndex] ? days[newIndex].iso : null;
      dayBarEl.querySelectorAll("[data-day-index]").forEach(function (chip) {
        var idx = parseInt(chip.getAttribute("data-day-index"), 10);
        var selected = idx === state.dayIndex;
        chip.classList.toggle("is-selected", selected);
        chip.setAttribute("aria-pressed", selected ? "true" : "false");
      });
      loadDay(state.dayIndex);
    });

    // If the cart already has a day picked (e.g. from Basket) that isn't
    // day 0, jump straight to it on load — same as order.js's own check.
    var storedIso = window.BKCart ? window.BKCart.getDayIso() : null;
    if (storedIso) {
      var foundIdx = -1;
      for (var i = 0; i < days.length; i++) {
        if (days[i].iso === storedIso) { foundIdx = i; break; }
      }
      if (foundIdx > 0) {
        state.dayIndex = foundIdx;
        state.dayIso = storedIso;
        dayBarEl.querySelectorAll("[data-day-index]").forEach(function (chip) {
          var idx = parseInt(chip.getAttribute("data-day-index"), 10);
          var selected = idx === state.dayIndex;
          chip.classList.toggle("is-selected", selected);
          chip.setAttribute("aria-pressed", selected ? "true" : "false");
        });
        loadDay(state.dayIndex);
      }
    }
  });
})();
