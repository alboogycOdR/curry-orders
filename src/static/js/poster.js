// poster.js — shared page interactions for the /v2/ poster variant.
// Loaded on every v2 page (base_v2.html, after cart.js). Talks to the
// same window.BKCart every Broadsheet script uses (see cart.js's own
// route-v2 storage-key branch) — this file only ever renders/reads
// state through that one API, never touching localStorage directly.
//
// Responsibilities:
//   - basket drawer (open/close, render lines from BKCart, qty +/-)
//   - order-lookup modal (open/close only — the form is a real POST)
//   - Escape/backdrop closing, matching guide §13
//   - category filter chips (home page's menu section)
//   - collection-slot picking (home page's collection panel)
//   - .pv-pay radio row highlight (checkout page's payment/collection choices)
// Dish "+" buttons call window.BKItemSheet.open(dishId) directly (see
// _item_sheet_v2.html) — same wiring order.js uses for the Broadsheet
// menu, just delegated from #pv-menu-cards instead of #menu.
(function () {
  "use strict";

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var overlayRoot = document.getElementById("pv-overlay-root");
    var drawer = document.getElementById("pv-drawer");
    var lookupModal = document.getElementById("pv-lookup-modal");
    if (!overlayRoot) return; // not a /v2/ page using base_v2.html

    var lastFocused = null;

    function anyOpen() {
      return !drawer.hidden || !lookupModal.hidden;
    }

    function showOverlayRoot() {
      overlayRoot.hidden = false;
    }
    function hideOverlayRootIfNoneOpen() {
      if (!anyOpen()) overlayRoot.hidden = true;
    }

    // ---------------------------------------------------------------- basket drawer

    function renderDrawer() {
      var body = document.getElementById("pv-drawer-body");
      var foot = document.getElementById("pv-drawer-foot");
      var totalEl = document.getElementById("pv-drawer-total");
      var holdEl = document.getElementById("pv-drawer-hold");
      var checkoutLink = document.getElementById("pv-drawer-checkout");
      if (!body || !window.BKCart) return;

      var lines = window.BKCart.getLines();
      if (!lines.length) {
        body.innerHTML =
          '<div class="pv-empty"><h3>Empty</h3>' +
          "<p>Your basket has nothing in it yet.</p>" +
          '<a href="' + (window.BK_V2_URLS ? window.BK_V2_URLS.menu : "#menu") +
          '" class="pv-btn pv-btn-dark" data-action="close-overlays">Browse the menu</a></div>';
        foot.hidden = true;
        return;
      }

      var html = "";
      lines.forEach(function (line) {
        var optParts = [];
        if (line.heat) optParts.push(escapeHtml(line.heat));
        if (line.extras && line.extras.length) {
          line.extras.forEach(function (ex) { optParts.push(escapeHtml(ex.name)); });
        }
        html +=
          '<div class="pv-bline" data-line-id="' + escapeHtml(line.id) + '">' +
          "<div>" +
          '<div class="pv-bline-name">' + escapeHtml(line.name) + "</div>" +
          (optParts.length ? '<div class="pv-bline-meta">' + optParts.join(" · ") + "</div>" : "") +
          '<div class="pv-qty" style="margin-left:0;margin-top:8px;">' +
          '<button type="button" data-action="drawer-dec" data-line-id="' + escapeHtml(line.id) + '" aria-label="One fewer">&minus;</button>' +
          "<span>" + line.qty + "</span>" +
          '<button type="button" class="plus" data-action="drawer-inc" data-line-id="' + escapeHtml(line.id) + '" aria-label="One more">+</button>' +
          "</div>" +
          "</div>" +
          '<div class="pv-bline-right"><div class="pv-bline-total">' + window.BKCart.rands(line.qty * line.unitPrice) + "</div></div>" +
          "</div>";
      });
      body.innerHTML = html;

      var t = window.BKCart.totals();
      totalEl.textContent = window.BKCart.rands(t.total);
      var day = window.BKCart.getDayIso();
      var slot = window.BKCart.getSlot();
      if (slot) {
        holdEl.textContent = "Collecting " + slot + (day ? " on " + day : "") + ". Slot held while you check out.";
      } else {
        holdEl.textContent = "Pick a collection window on the home page before checking out.";
      }
      var ready = t.count > 0 && !!window.BKCart.getSlotId();
      checkoutLink.setAttribute("aria-disabled", ready ? "false" : "true");
      checkoutLink.style.opacity = ready ? "" : ".5";
      checkoutLink.style.pointerEvents = ready ? "" : "none";
      foot.hidden = false;
    }

    function openDrawer() {
      lastFocused = document.activeElement;
      showOverlayRoot();
      renderDrawer();
      drawer.hidden = false;
      var closeBtn = drawer.querySelector(".pv-x");
      if (closeBtn) closeBtn.focus();
    }

    function openLookup() {
      lastFocused = document.activeElement;
      showOverlayRoot();
      lookupModal.hidden = false;
      var firstInput = lookupModal.querySelector("input");
      if (firstInput) firstInput.focus();
    }

    function closeOverlays() {
      drawer.hidden = true;
      lookupModal.hidden = true;
      hideOverlayRootIfNoneOpen();
      if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus();
    }

    document.addEventListener("click", function (e) {
      // pointer-events:none (set in renderDrawer) already blocks a mouse
      // click on the disabled checkout link; aria-disabled alone doesn't
      // stop keyboard Enter activating an <a>, so guard that here too.
      var checkoutLinkClick = e.target.closest("#pv-drawer-checkout");
      if (checkoutLinkClick && checkoutLinkClick.getAttribute("aria-disabled") === "true") {
        e.preventDefault();
        return;
      }
      var openBasketTrigger = e.target.closest('[data-action="open-basket"]');
      if (openBasketTrigger) { e.preventDefault(); openDrawer(); return; }
      var openLookupTrigger = e.target.closest('[data-action="open-lookup"]');
      if (openLookupTrigger) { e.preventDefault(); openLookup(); return; }
      var closeTrigger = e.target.closest('[data-action="close-overlays"]');
      if (closeTrigger) { e.preventDefault(); closeOverlays(); return; }

      var decBtn = e.target.closest('[data-action="drawer-dec"]');
      if (decBtn) {
        var lines1 = window.BKCart.getLines();
        var line1 = lines1.filter(function (l) { return l.id === decBtn.getAttribute("data-line-id"); })[0];
        if (line1) window.BKCart.updateLine(line1.id, { qty: line1.qty - 1 });
        renderDrawer();
        return;
      }
      var incBtn = e.target.closest('[data-action="drawer-inc"]');
      if (incBtn) {
        var lines2 = window.BKCart.getLines();
        var line2 = lines2.filter(function (l) { return l.id === incBtn.getAttribute("data-line-id"); })[0];
        if (line2) window.BKCart.updateLine(line2.id, { qty: line2.qty + 1 });
        renderDrawer();
        return;
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && anyOpen()) closeOverlays();
    });

    // Cross-tab / cross-line updates while the drawer is open.
    window.addEventListener("storage", function (e) {
      if (e.key === window.BKCart.STORAGE_KEY && !drawer.hidden) renderDrawer();
    });
    document.addEventListener("bkItemSheet:added", function () {
      if (!drawer.hidden) renderDrawer();
    });
    document.addEventListener("bkItemSheet:updated", function () {
      if (!drawer.hidden) renderDrawer();
    });

    // ---------------------------------------------------------------- menu "+" -> item sheet

    var menuCards = document.getElementById("pv-menu-cards");
    if (menuCards) {
      menuCards.addEventListener("click", function (e) {
        var addBtn = e.target.closest(".pv-add[data-dish-id]");
        if (!addBtn) return;
        var itemId = parseInt(addBtn.getAttribute("data-dish-id"), 10);
        if (itemId && window.BKItemSheet) window.BKItemSheet.open(itemId);
      });
    }

    // ---------------------------------------------------------------- category filters

    var filterBar = document.getElementById("pv-filters");
    if (filterBar) {
      filterBar.addEventListener("click", function (e) {
        var chip = e.target.closest(".pv-filter");
        if (!chip) return;
        filterBar.querySelectorAll(".pv-filter").forEach(function (c) {
          c.classList.toggle("is-on", c === chip);
          c.setAttribute("aria-selected", c === chip ? "true" : "false");
        });
        var cat = chip.getAttribute("data-filter");
        document.querySelectorAll("#pv-menu-cards .pv-card").forEach(function (card) {
          var show = cat === "all" || card.getAttribute("data-category") === cat;
          card.hidden = !show;
        });
      });
    }

    // ---------------------------------------------------------------- collection slot picking

    var slotGrid = document.getElementById("pv-collection-slots");
    if (slotGrid) {
      slotGrid.addEventListener("click", function (e) {
        var chip = e.target.closest(".pv-slot");
        if (!chip || chip.disabled) return;
        slotGrid.querySelectorAll(".pv-slot").forEach(function (c) { c.classList.remove("is-on"); });
        chip.classList.add("is-on");
        window.BKCart.setSlotId(chip.getAttribute("data-slot-id"));
        window.BKCart.setSlot(chip.getAttribute("data-slot-label"));
        window.BKCart.setDayIso(slotGrid.getAttribute("data-day-iso"));
      });
    }

    // ---------------------------------------------------------------- .pv-pay radio highlight
    // Generic: any .pv-pay wrapping a radio gets .is-on synced to it —
    // used by both the payment-method and collection-method groups on
    // the checkout page.

    document.querySelectorAll(".pv-pay").forEach(function (row) {
      var radio = row.querySelector('input[type="radio"]');
      if (!radio) return;
      radio.addEventListener("change", function () {
        document.querySelectorAll('input[name="' + radio.name + '"]').forEach(function (r) {
          var wrap = r.closest(".pv-pay");
          if (wrap) wrap.classList.toggle("is-on", r.checked);
        });
      });
    });
  });
})();
