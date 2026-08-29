// payments.js — the EFT payment queue (spec §12.3). Row actions POST to
// `manage:api_transition` (staff/api.py), which runs the real
// `core.transitions.apply()` — no polling yet (§12.1 asks for 15s HTMX
// polling; this page just says "reload to see other staff's changes"
// for now, see payments.html's own note).
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

  document.addEventListener("DOMContentLoaded", function () {
    var body = document.getElementById("pq-body");
    if (!body) return;

    body.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action]");
      if (!btn || btn.disabled) return;
      var row = btn.closest("tr");
      var errorEl = row.querySelector(".pq-row-error");
      var action = btn.getAttribute("data-action");
      var orderId = row.getAttribute("data-order-id");
      var expectedStatus = row.getAttribute("data-status");

      var reason = null;
      if (btn.getAttribute("data-needs-reason")) {
        reason = window.prompt("Reason (required):");
        if (!reason) return; // cancelled or left blank — don't fire the request
      }

      errorEl.hidden = true;
      errorEl.textContent = "";
      row.querySelectorAll("button").forEach(function (b) { b.disabled = true; });

      fetch("/manage/api/orders/" + orderId + "/transition", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          action: action,
          expected_status: expectedStatus,
          reason: reason,
        }),
        credentials: "same-origin",
      })
        .then(function (resp) {
          return resp.json().then(function (responseBody) {
            return { ok: resp.ok, status: resp.status, body: responseBody };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            row.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
            var message = (result.body && result.body.message) || "That didn't work — try again.";
            if (result.status === 409) {
              message += " Reload the page to see the current state.";
            }
            errorEl.textContent = message;
            errorEl.hidden = false;
            return;
          }
          // Every action here changes something about the row (status,
          // hold countdown, which buttons are legal next) — a full
          // reload is the simplest correct way to show that without a
          // client-side row-patching system this pass doesn't build
          // (no polling either, see payments.html's own note).
          window.location.reload();
        })
        .catch(function () {
          row.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
          errorEl.textContent = "Couldn't reach the server — check your connection and try again.";
          errorEl.hidden = false;
        });
    });
  });
})();
