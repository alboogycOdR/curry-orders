// cash_requests.js — the cash requests queue (spec §12.2's own item,
// milestone 7). Accept/Reject via the shared manage:api_transition
// endpoint, same pattern as payments.js/kitchen.js/collection.js.
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
    var body = document.getElementById("cr-body");
    if (!body) return;

    body.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action]");
      if (!btn || btn.disabled) return;
      var row = btn.closest("tr");
      var errorEl = row.querySelector(".cr-row-error");
      var action = btn.getAttribute("data-action");
      var orderId = row.getAttribute("data-order-id");
      var expectedStatus = row.getAttribute("data-status");

      var reason = null;
      if (action === "reject_cash") {
        reason = window.prompt("Reason (optional):") || null;
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
        body: JSON.stringify({ action: action, expected_status: expectedStatus, reason: reason }),
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
            errorEl.textContent = (result.body && result.body.message) || "That didn't work.";
            errorEl.hidden = false;
            return;
          }
          window.location.reload();
        })
        .catch(function () {
          row.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
          errorEl.textContent = "Couldn't reach the server.";
          errorEl.hidden = false;
        });
    });
  });
})();
