// collection.js — the collection board (spec §12.5). Per-ticket
// mark_ready/mark_collected/uncollect/close_out_no_show via the shared
// `manage:api_transition` endpoint, plus the day-level "Close out day"
// button. No polling yet, same as kitchen.js/payments.js.
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

  function currentDate() {
    var params = new URLSearchParams(window.location.search);
    return params.get("date") || new Date().toISOString().slice(0, 10);
  }

  // Mirrors core.money.format_cents' grouping, same as cart.js's rands()
  // — used only to pre-fill the Collected-amount prompt with a number a
  // human can read and edit, not sent anywhere as a display string.
  function randsFromCents(cents) {
    return (cents / 100).toFixed(2);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.body.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action]");
      if (!btn || btn.disabled) return;
      var ticket = btn.closest("[data-order-id]");
      var errorEl = ticket.querySelector(".cb-row-error");
      var action = btn.getAttribute("data-action");
      var orderId = ticket.getAttribute("data-order-id");
      var expectedStatus = ticket.getAttribute("data-status");

      var payload = {};
      var reason = null;

      if (action === "mark_collected" && ticket.dataset.totalCents !== undefined) {
        // Cash only — EFT tickets never render this button with a
        // meaningful total prompt needed since nothing to confirm.
        var isCash = ticket.querySelector(".tag-outline") !== null;
        if (isCash) {
          var totalCents = parseInt(ticket.getAttribute("data-total-cents"), 10);
          var entered = window.prompt(
            "Cash amount received (R):", randsFromCents(totalCents),
          );
          if (entered === null) return; // cancelled
          var cents = Math.round(parseFloat(entered) * 100);
          if (isNaN(cents) || cents < 0) {
            errorEl.textContent = "Enter a valid amount.";
            errorEl.hidden = false;
            return;
          }
          payload.cash_amount_received_cents = cents;
        }
      }

      if (btn.getAttribute("data-needs-reason")) {
        reason = window.prompt("Reason (required):");
        if (!reason) return;
      }

      errorEl.hidden = true;
      errorEl.textContent = "";
      ticket.querySelectorAll("button").forEach(function (b) { b.disabled = true; });

      fetch("/manage/api/orders/" + orderId + "/transition", {
        method: "POST",
        headers: csrfHeaders(),
        body: JSON.stringify({
          action: action, expected_status: expectedStatus, reason: reason, payload: payload,
        }),
        credentials: "same-origin",
      })
        .then(function (resp) {
          return resp.json().then(function (body) {
            return { ok: resp.ok, status: resp.status, body: body };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            ticket.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
            errorEl.textContent = (result.body && result.body.message) || "That didn't work.";
            errorEl.hidden = false;
            return;
          }
          window.location.reload();
        })
        .catch(function () {
          ticket.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
          errorEl.textContent = "Couldn't reach the server.";
          errorEl.hidden = false;
        });
    });

    var closeOutBtn = document.getElementById("cb-close-out-btn");
    if (closeOutBtn) {
      closeOutBtn.addEventListener("click", function () {
        if (!window.confirm("Close out the day? Every remaining ready order becomes a no-show.")) return;
        closeOutBtn.disabled = true;
        fetch("/manage/api/days/" + currentDate() + "/close-out", {
          method: "POST",
          headers: csrfHeaders(),
          credentials: "same-origin",
        })
          .then(function () { window.location.reload(); })
          .catch(function () { closeOutBtn.disabled = false; });
      });
    }
  });
})();
