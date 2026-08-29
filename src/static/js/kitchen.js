// kitchen.js — the Kitchen desk status-tag advance (design handoff
// §"Screens" §4). Purely client-side and forward-only, same as the
// handoff's own reducer; a reload resets to the server-rendered sample
// data. Real state changes are a POST per transition through
// `core.transitions.apply()` (milestone 5/6) — see staff/views.py.
(function () {
  "use strict";

  function readJSONScript(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return fallback;
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var statuses = readJSONScript("kd-statuses", []);
    var tagClass = readJSONScript("kd-status-tag-class", {});
    var body = document.getElementById("kd-run-body");
    if (!body || !statuses.length) return;

    body.addEventListener("click", function (e) {
      var btn = e.target.closest(".kd-status-btn");
      if (!btn) return;
      var idx = parseInt(btn.getAttribute("data-status-index"), 10);
      idx = Math.min(idx + 1, statuses.length - 1);
      var status = statuses[idx];
      btn.setAttribute("data-status-index", idx);
      btn.textContent = status;
      btn.setAttribute("class", (tagClass[status] || "tag") + " kd-status-btn");
    });
  });
})();
