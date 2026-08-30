// share-link.js — the "Copy / share link" button on checkout.html's
// confirmation panel and order_status.html (spec §13's "Order created"
// row: "On-screen + token URL + Copy/Share" — this is the Copy/Share
// third of it). Shared rather than duplicated in both pages: the
// fallback chain is the same in each place, just wired to a different
// URL/button.
//
// Three tiers, in order of how good the result is — each one only
// attempted if the previous isn't available:
//   1. navigator.share() — the native share sheet (Android Chrome/iOS
//      Safari).
//   2. navigator.clipboard.writeText() — silent copy, "Link copied"
//      shown.
//   3. A visible, pre-filled, auto-selected <input readonly> — works
//      with no permissions and no secure-context requirement, which
//      matters right now: both 1 and 2 require HTTPS in most browsers,
//      and the current deploy is plain HTTP at a raw IP:port (pending a
//      real domain/TLS) — so on today's live site, this fallback is the
//      one actually doing the work. It upgrades to the nicer tiers for
//      free the day TLS is turned on, no code change needed.
window.BKShareLink = (function () {
  "use strict";

  function revealFallback(opts) {
    opts.input.value = opts.url;
    opts.fallback.hidden = false;
    opts.input.focus();
    opts.input.select();
  }

  function showStatus(opts, message) {
    if (!opts.status) return;
    opts.status.textContent = message;
    opts.status.hidden = false;
  }

  // opts: { button, fallback, input, status (optional), url, title,
  //         onBeforeShare (optional) }
  function wire(opts) {
    opts.button.addEventListener("click", function () {
      if (opts.onBeforeShare) opts.onBeforeShare();

      if (navigator.share) {
        navigator.share({ title: opts.title, url: opts.url }).catch(function () {
          // AbortError (user cancelled the share sheet) or any other
          // failure — fall back to showing the link so they still have
          // a way to grab it manually.
          revealFallback(opts);
        });
        return;
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(opts.url).then(function () {
          showStatus(opts, "Link copied.");
        }).catch(function () {
          revealFallback(opts);
        });
        return;
      }

      revealFallback(opts);
    });
  }

  return { wire: wire };
})();
