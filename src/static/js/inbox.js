// inbox.js — the staff inbox (spec §12.2). One shared click handler for
// every section's row actions (Accept/Reject cash, Assign, Reinstate,
// Move slot) — same request pattern payments.js/cash_requests.js already
// use against `manage:api_transition`, plus the plain toggle endpoint
// `manage:api_assign_order` for "assign"/"unassign" (not a state-machine
// transition, so it isn't routed through core.transitions.apply()).
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

  function postJSON(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
      body: JSON.stringify(body),
      credentials: "same-origin",
    }).then(function (resp) {
      return resp.json().then(function (responseBody) {
        return { ok: resp.ok, status: resp.status, body: responseBody };
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var root = document.getElementById("ib-root");
    if (!root) return;

    root.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action]");
      if (!btn || btn.disabled) return;
      var row = btn.closest("tr");
      var errorEl = row.querySelector(".ib-row-error");
      var action = btn.getAttribute("data-action");
      var orderId = row.getAttribute("data-order-id");
      var expectedStatus = row.getAttribute("data-status");

      var reason = null;
      if (btn.getAttribute("data-needs-reason")) {
        reason = window.prompt("Reason (required):");
        if (!reason) return; // cancelled or left blank — don't fire the request
      }

      var url;
      var body;
      if (action === "assign") {
        url = "/manage/api/orders/" + orderId + "/assign";
        body = {};
      } else if (action === "change_slot") {
        var select = row.querySelector("select[name=new_slot_id]");
        if (!select || !select.value) return;
        url = "/manage/api/orders/" + orderId + "/transition";
        body = {
          action: "change_slot", expected_status: expectedStatus,
          payload: { new_slot_id: parseInt(select.value, 10) },
        };
      } else {
        url = "/manage/api/orders/" + orderId + "/transition";
        body = { action: action, expected_status: expectedStatus, reason: reason };
      }

      errorEl.hidden = true;
      errorEl.textContent = "";
      row.querySelectorAll("button").forEach(function (b) { b.disabled = true; });

      postJSON(url, body)
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
