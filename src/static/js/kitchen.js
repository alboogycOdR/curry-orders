// kitchen.js — the kitchen desk (spec §12.4). Per-row start_kitchen/
// mark_ready plus the two bulk buttons, all through the same
// `manage:api_transition` endpoint `static/js/payments.js` uses, and
// the day-level "Lock prep list" endpoint. No polling yet (§12.1 asks
// for 30s refresh; this page just says "reload" for now).
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

  function csrfHeaders() {
    return { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") };
  }

  function fireTransition(orderId, action, expectedStatus) {
    return fetch("/manage/api/orders/" + orderId + "/transition", {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify({ action: action, expected_status: expectedStatus }),
      credentials: "same-origin",
    }).then(function (resp) {
      return resp.json().then(function (body) {
        return { ok: resp.ok, status: resp.status, body: body };
      });
    });
  }

  function currentDate() {
    var params = new URLSearchParams(window.location.search);
    return params.get("date") || new Date().toISOString().slice(0, 10);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var lockBtn = document.getElementById("kd-lock-btn");
    if (lockBtn) {
      lockBtn.addEventListener("click", function () {
        lockBtn.disabled = true;
        fetch("/manage/api/days/" + currentDate() + "/lock-kitchen", {
          method: "POST",
          headers: csrfHeaders(),
          credentials: "same-origin",
        })
          .then(function () { window.location.reload(); })
          .catch(function () { lockBtn.disabled = false; });
      });
    }

    var body = document.getElementById("kd-run-body");
    if (body) {
      body.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-action]");
        if (!btn || btn.disabled) return;
        var row = btn.closest("tr");
        var errorEl = row.querySelector(".kd-row-error");
        row.querySelectorAll("button").forEach(function (b) { b.disabled = true; });

        fireTransition(row.getAttribute("data-order-id"), btn.getAttribute("data-action"), row.getAttribute("data-status"))
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
    }

    function bulkFire(action) {
      var rows = Array.prototype.slice.call(
        document.querySelectorAll("#kd-run-body tr[data-status]"),
      ).filter(function (row) {
        return row.querySelector("[data-action='" + action + "']");
      });
      if (!rows.length) return;
      var chain = Promise.resolve();
      rows.forEach(function (row) {
        chain = chain.then(function () {
          return fireTransition(row.getAttribute("data-order-id"), action, row.getAttribute("data-status"));
        });
      });
      chain.then(function () { window.location.reload(); });
    }

    var bulkStart = document.getElementById("kd-bulk-start");
    if (bulkStart) bulkStart.addEventListener("click", function () { bulkFire("start_kitchen"); });
    var bulkReady = document.getElementById("kd-bulk-ready");
    if (bulkReady) bulkReady.addEventListener("click", function () { bulkFire("mark_ready"); });
  });
})();
