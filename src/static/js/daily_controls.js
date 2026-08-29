// daily_controls.js — the "Move all to…" helper on the confirmation
// banner (spec §12.8). A separate fetch() before the main form's own
// submit, not part of it — moving orders off a slot changes its
// occupancy to 0, so the simplest correct next step is just reloading
// the page: the confirmation banner (server-computed) drops away on
// its own once nothing is left to confirm.
(function () {
  "use strict";

  function getCookie(name) {
    var prefix = name + "=";
    var parts = document.cookie ? document.cookie.split("; ") : [];
    for (var i = 0; i < parts.length; i++) {
      if (parts[i].indexOf(prefix) === 0) return decodeURIComponent(parts[i].slice(prefix.length));
    }
    return null;
  }

  function currentDate() {
    var parts = window.location.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1]; // /manage/days/<date>/
  }

  document.addEventListener("DOMContentLoaded", function () {
    var banner = document.getElementById("dc-confirm-banner");
    if (!banner) return;

    banner.querySelectorAll(".dc-move-row").forEach(function (row) {
      var btn = row.querySelector(".dc-move-btn");
      var select = row.querySelector(".dc-move-target");
      var resultEl = row.querySelector(".dc-move-result");
      var slotId = row.getAttribute("data-slot-id");

      btn.addEventListener("click", function () {
        var toSlotId = select.value;
        if (!toSlotId) {
          resultEl.textContent = "Choose a slot first.";
          return;
        }
        btn.disabled = true;
        resultEl.textContent = "Moving…";

        fetch("/manage/api/days/" + currentDate() + "/slots/" + slotId + "/move-all", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
          },
          body: JSON.stringify({ to_slot_id: parseInt(toSlotId, 10) }),
          credentials: "same-origin",
        })
          .then(function (resp) { return resp.json(); })
          .then(function (body) {
            resultEl.textContent = body.moved + " moved" +
              (body.failures && body.failures.length ? ", " + body.failures.length + " failed" : "") + ".";
            window.setTimeout(function () { window.location.reload(); }, 800);
          })
          .catch(function () {
            btn.disabled = false;
            resultEl.textContent = "Couldn't reach the server.";
          });
      });
    });
  });
})();
