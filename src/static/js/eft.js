// eft.js — the EFT panel on the order status page (spec §11.7):
// server-time hold countdown and the proof-upload control. Loaded only
// when `order_status.html` actually renders the panel (an EFT order
// still `awaiting_eft`/`payment_review`).
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

  function formatRemaining(ms) {
    var totalSeconds = Math.max(0, Math.floor(ms / 1000));
    var minutes = Math.floor(totalSeconds / 60);
    var seconds = totalSeconds % 60;
    return minutes + ":" + (seconds < 10 ? "0" : "") + seconds;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var panel = document.getElementById("os-eft-panel");
    if (!panel) return;

    var countdownEl = document.getElementById("os-eft-countdown");
    var holdExpiresAtRaw = panel.getAttribute("data-hold-expires-at");
    // §11.7: "countdown to hold_expires_at (server time, not client
    // clock)" — the page's initial render *is* the server time this
    // reads from (Django rendered `data-hold-expires-at` at request
    // time); ticking it down locally after that is the same trade-off
    // any countdown makes rather than polling the server every second.
    var holdExpiresAt = holdExpiresAtRaw ? new Date(holdExpiresAtRaw) : null;

    function tickCountdown() {
      if (!holdExpiresAt || isNaN(holdExpiresAt.getTime())) {
        countdownEl.textContent = "";
        return;
      }
      var remaining = holdExpiresAt.getTime() - Date.now();
      if (remaining <= 0) {
        countdownEl.textContent = "Payment window has closed";
        countdownEl.classList.add("is-expired");
        clearInterval(countdownTimer);
        return;
      }
      countdownEl.textContent = "Pay within " + formatRemaining(remaining);
    }
    tickCountdown();
    var countdownTimer = setInterval(tickCountdown, 1000);

    var fileInput = document.getElementById("os-upload-input");
    var submitBtn = document.getElementById("os-upload-submit");
    var statusEl = document.getElementById("os-upload-status");
    var uploadBlock = document.getElementById("os-upload-block");
    if (!fileInput || !submitBtn) return; // already uploaded — no control to wire

    function setStatus(message, kind) {
      statusEl.textContent = message;
      statusEl.hidden = !message;
      statusEl.classList.remove("is-ok", "is-error");
      if (kind) statusEl.classList.add(kind);
    }

    fileInput.addEventListener("change", function () {
      submitBtn.disabled = !fileInput.files || fileInput.files.length === 0;
      setStatus("", null);
    });

    submitBtn.addEventListener("click", function () {
      if (!fileInput.files || fileInput.files.length === 0) return;
      var file = fileInput.files[0];

      submitBtn.disabled = true;
      fileInput.disabled = true;
      setStatus("Uploading…", null);

      var formData = new FormData();
      formData.append("file", file);

      fetch(panel.getAttribute("data-upload-url"), {
        method: "POST",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
        body: formData,
        credentials: "same-origin",
      })
        .then(function (resp) {
          return resp.json().then(function (body) {
            return { ok: resp.ok, body: body };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            submitBtn.disabled = false;
            fileInput.disabled = false;
            setStatus((result.body && result.body.message) || "Upload failed — try again.", "is-error");
            return;
          }
          // Matches what the server renders when `proof_already_uploaded`
          // is true from the start (order_status.html) — `uploadBlock`
          // already carries `.os-upload`'s top border/spacing, so this
          // only swaps its inner content, not the wrapper.
          uploadBlock.innerHTML = "Your proof is with us — no further action needed.";
          var statusCopy = document.getElementById("os-status-copy");
          if (statusCopy) {
            statusCopy.textContent = "Payment received — a staff member is confirming it.";
          }
        })
        .catch(function () {
          submitBtn.disabled = false;
          fileInput.disabled = false;
          setStatus("Couldn't reach the server — check your connection and try again.", "is-error");
        });
    });
  });
})();
