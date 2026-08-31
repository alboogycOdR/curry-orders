// order.js — Menu screen (PR 5). Sticky filter chips and item sheet overlay.
// Day/slot picker + Continue moved to /basket/ (PR 5).
//
// Clicking a non-sold-out dish row (or its + button) opens BKItemSheet.open().
// Navigating to a hash (#roti, #gatsby …) shows that chip section.
(function () {
  "use strict";

  function escapeHtml(s) {
    var div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var menuEl    = document.getElementById("op-menu");
    var filterBar = document.getElementById("op-filter-bar");

    if (!menuEl) return;

    // ---- chip section navigation ----

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

    // ---- initial hash navigation ----

    var hash = (location.hash || "").replace(/^#/, "");
    if (hash) showChip(hash);
  });
})();
