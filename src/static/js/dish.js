// dish.js — the Dish detail screen (spec §11.4): qty stepper, option
// selection, Add to cart. PR 4: uses BKCart v2 API (upsertLine).
// Dish detail is a progressive-enhancement permalink for WhatsApp/IG
// sharing; /order/ and /basket/ use the item sheet overlay instead.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("dd-form");
    if (!form) return;

    var dishId    = parseInt(form.dataset.dishId, 10);
    var dishName  = form.dataset.dishName;
    var basePrice = parseFloat(form.dataset.basePrice);

    var qtyEl       = document.getElementById("dd-qty-count");
    var decBtn      = document.getElementById("dd-qty-dec");
    var incBtn      = document.getElementById("dd-qty-inc");
    var addBtn      = document.getElementById("dd-add");
    var confirmEl   = document.getElementById("dd-confirm");
    var confirmText = document.getElementById("dd-confirm-text");

    // #dd-add is absent on sold-out dish pages (no Add button rendered).
    if (!addBtn) return;

    var qty = 1;
    var MIN_QTY = 1;
    var MAX_QTY = 20;

    // Fix default selection: if the pre-checked radio in a required group is
    // disabled, uncheck it and select the first available option instead.
    form.querySelectorAll("input[type=radio]").forEach(function (radio) {
      if (radio.checked && radio.disabled) {
        radio.checked = false;
        var first = form.querySelector(
          "input[type=radio][name=\"" + radio.name + "\"]:not([disabled])"
        );
        if (first) first.checked = true;
      }
    });

    // Format cents as South African Rand, e.g. 18000 → "R 180.00"
    function formatRand(cents) {
      var amount = (cents / 100).toFixed(2);
      var parts  = amount.split(".");
      parts[0]   = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
      return "R " + parts[0] + "." + parts[1];
    }

    // Compute current unit price (base + any checked option deltas)
    function currentUnitPrice() {
      var delta = 0;
      form.querySelectorAll("input[type=radio]:checked, input[type=checkbox]:checked").forEach(function (input) {
        delta += parseFloat(input.dataset.delta) || 0;
      });
      return basePrice + delta;
    }

    // Update CTA button text to show "Add {qty} for R {total}"
    function renderTotal() {
      if (!addBtn) return;
      var total = currentUnitPrice() * qty;
      addBtn.textContent = "Add " + qty + " for " + formatRand(total);
    }

    function renderQty() {
      qtyEl.textContent = qty;
      decBtn.disabled = qty <= MIN_QTY;
      incBtn.disabled = qty >= MAX_QTY;
      renderTotal();
    }

    decBtn.addEventListener("click", function () {
      qty = Math.max(MIN_QTY, qty - 1);
      renderQty();
    });
    incBtn.addEventListener("click", function () {
      qty = Math.min(MAX_QTY, qty + 1);
      renderQty();
    });

    // Re-render total whenever any option changes
    form.addEventListener("change", function (e) {
      if (e.target.matches("input[type=radio], input[type=checkbox]")) {
        renderTotal();
      }
    });

    function selectedOptions() {
      var selected = [];
      form.querySelectorAll("input[type=radio], input[type=checkbox]").forEach(function (input) {
        if (!input.checked) return;
        var label = input.closest(".dd-option-row").querySelector("span");
        selected.push({
          id:      parseInt(input.value, 10),
          name:    label ? label.textContent.trim() : "",
          delta:   parseFloat(input.dataset.delta) || 0,
          optName: (input.closest(".dd-section") &&
                    input.closest(".dd-section").querySelector(".dd-section-label"))
                   ? input.closest(".dd-section").querySelector(".dd-section-label")
                       .textContent.replace(/\s*\(optional\)\s*$/, "").trim()
                   : "",
        });
      });
      return selected;
    }

    addBtn.addEventListener("click", function () {
      var options   = selectedOptions();
      var optionIds = options.map(function (o) { return o.id; }).sort(function (a, b) { return a - b; });
      var priceDelta = options.reduce(function (sum, o) { return sum + o.delta; }, 0);
      var unitPrice  = basePrice + priceDelta;

      // Determine heat label (Spice group)
      var heat   = "";
      var extras = [];
      options.forEach(function (o) {
        if (o.optName === "Spice") heat = o.name;
        else if (o.delta !== 0) extras.push({ optionValueId: o.id, name: o.name, deltaCents: o.delta });
      });

      var id = optionIds.length ? String(dishId) + ":" + optionIds.join(",") : String(dishId);
      var nameSuffix = options.length
        ? " (" + options.map(function (o) { return o.name; }).join(", ") + ")"
        : "";

      window.BKCart.upsertLine({
        id:             id,
        itemId:         dishId,
        name:           dishName + nameSuffix,
        heat:           heat,
        extras:         extras,
        notes:          "",
        qty:            qty,
        unitPrice:      unitPrice,
        lineTotal:      unitPrice * qty,
        photoUrl:       "",
        optionValueIds: optionIds,
      });
      if (confirmText) confirmText.textContent = "Added to your order.";
      confirmEl.classList.add("is-visible");
    });

    renderQty();
  });
})();
