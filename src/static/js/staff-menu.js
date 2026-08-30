// staff-menu.js — the header "Staff" dropdown (base.html), replacing
// the old flat row of 7 nav links that ran off the edge of a phone
// screen. Only loaded when request.staff_user is set (base.html), so
// no anonymous visitor ever fetches this for nothing.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var menu = document.getElementById("staff-menu");
    if (!menu) return;
    var toggle = document.getElementById("staff-menu-toggle");
    var panel = document.getElementById("staff-menu-panel");

    function open() {
      menu.setAttribute("data-open", "true");
      toggle.setAttribute("aria-expanded", "true");
      panel.hidden = false;
    }
    function close() {
      menu.removeAttribute("data-open");
      toggle.setAttribute("aria-expanded", "false");
      panel.hidden = true;
    }
    function isOpen() {
      return !panel.hidden;
    }

    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      if (isOpen()) close(); else open();
    });

    // Click anywhere outside the menu closes it.
    document.addEventListener("click", function (e) {
      if (isOpen() && !menu.contains(e.target)) close();
    });

    // Escape closes it and returns focus to the toggle, same as any
    // standard menu/disclosure widget.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && isOpen()) {
        close();
        toggle.focus();
      }
    });
  });
})();
