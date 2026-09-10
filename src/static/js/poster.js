// poster.js — shared page interactions for the poster variant.
// Loaded on every page (base_v2.html, after cart.js).
//
// Basket is a real page now (v2:basket, reusing basket.js verbatim),
// not a drawer, and order lookup is a real page (v2:lookup) reached
// from Account/the footer, not a modal — both dropped from here in the
// 2025-09 information-architecture review that aligned this variant
// with the Broadsheet site's own structure (see public/urls_v2.py's
// docstring). What's left:
//   - the "More" sheet (Help/Policies/Staff login), mirroring
//     base.html's #mobile-more-sheet almost verbatim
//   - category filter chips (Menu page)
//   - .pv-pay radio-row highlight (Checkout page's payment/collection
//     choices)
// Dish "+" buttons call window.BKItemSheet.open(dishId) directly (see
// _item_sheet_v2.html) — same wiring order.js uses for the Broadsheet
// menu, just delegated from #pv-menu-cards instead of #menu.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    // ---------------------------------------------------------------- More sheet

    var moreBtn = document.getElementById("pv-more-btn");
    var moreSheet = document.getElementById("pv-more-sheet");
    var moreBackdrop = document.getElementById("pv-more-backdrop");

    if (moreBtn && moreSheet) {
      function openMore() {
        moreSheet.hidden = false;
        moreBtn.setAttribute("aria-expanded", "true");
      }
      function closeMore() {
        moreSheet.hidden = true;
        moreBtn.setAttribute("aria-expanded", "false");
        moreBtn.focus();
      }
      moreBtn.addEventListener("click", function () {
        if (moreSheet.hidden) openMore(); else closeMore();
      });
      if (moreBackdrop) moreBackdrop.addEventListener("click", closeMore);
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && !moreSheet.hidden) closeMore();
      });
    }

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

  // A first sync pass belongs on window "load", not the DOMContentLoaded
  // block above: checkout.js's own renderPay() sets payEft/payCash.checked
  // programmatically from the customer's persisted BKCart.getPay() state,
  // inside *its own* DOMContentLoaded handler — registered after this
  // file's (checkout.js loads later in the document), so it runs *after*
  // this file's handler already fired. Setting `.checked` via JS also
  // never fires a native "change" event on its own. Net effect, found
  // live: the EFT row looked unselected on load despite the radio being
  // genuinely checked — syncing here once DOMContentLoaded is a
  // DOMContentLoaded handler too early; only Direct-collection looked
  // right, and only because that one option had .is-on hardcoded in the
  // template as a workaround. `load` fires strictly after every deferred
  // script's DOMContentLoaded handler has completed, so this reads the
  // final state regardless of script order — no changes to checkout.js
  // needed, and the template's hardcoded .is-on could come out.
  window.addEventListener("load", function () {
    document.querySelectorAll(".pv-pay").forEach(function (row) {
      var radio = row.querySelector('input[type="radio"]');
      if (radio) row.classList.toggle("is-on", radio.checked);
    });
  });
})();
