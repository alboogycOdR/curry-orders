// dish.js — the Dish detail screen (spec §11.4): qty stepper, option
// selection, Add to cart. Builds on the shared cart.js (cart.js's own
// header comment explains why the cart is localStorage-only for now).
//
// cart.js keys a cart line by a plain dish id, one qty/price/name per
// key — fine for a dish with no options, but two different option
// combinations of the *same* dish need to be two separate lines (a
// Mild and a Hot Full House Gatsby aren't the same order line). This
// page builds a composite key (`"<dishId>:<sorted option value ids>"`)
// so cart.js's existing API doesn't need to change to support that.
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("dd-form");
    if (!form) return; // sold-out-with-no-options-rendered / archived dish pages have no form

    var dishId = form.dataset.dishId;
    var dishName = form.dataset.dishName;
    var basePrice = parseFloat(form.dataset.basePrice);

    var qtyEl = document.getElementById("dd-qty-count");
    var decBtn = document.getElementById("dd-qty-dec");
    var incBtn = document.getElementById("dd-qty-inc");
    var addBtn = document.getElementById("dd-add");
    var confirmEl = document.getElementById("dd-confirm");

    var qty = 1;
    var MIN_QTY = 1;
    var MAX_QTY = 20; // spec §11.4: "quantity stepper (1-20)"

    function renderQty() {
      qtyEl.textContent = qty;
      decBtn.disabled = qty <= MIN_QTY;
      incBtn.disabled = qty >= MAX_QTY;
    }

    decBtn.addEventListener("click", function () {
      qty = Math.max(MIN_QTY, qty - 1);
      renderQty();
    });
    incBtn.addEventListener("click", function () {
      qty = Math.min(MAX_QTY, qty + 1);
      renderQty();
    });

    function selectedOptions() {
      // One entry per option group: the checked radio, or every checked
      // checkbox (an optional add-on group may contribute zero or more).
      var selected = []; // [{id, name, delta}]
      var seenGroups = {};
      form.querySelectorAll("input[type=radio], input[type=checkbox]").forEach(function (input) {
        if (!input.checked) return;
        var label = input.closest(".dd-option-row").querySelector("span");
        selected.push({
          id: input.value,
          name: label ? label.textContent.trim() : "",
          delta: parseFloat(input.dataset.delta) || 0,
        });
        seenGroups[input.name] = true;
      });
      return selected;
    }

    addBtn.addEventListener("click", function () {
      var options = selectedOptions();
      var optionIds = options.map(function (o) { return o.id; }).sort();
      var compositeId = optionIds.length ? dishId + ":" + optionIds.join(",") : dishId;
      var priceDelta = options.reduce(function (sum, o) { return sum + o.delta; }, 0);
      var unitPrice = basePrice + priceDelta;
      var optionSuffix = options.length
        ? " (" + options.map(function (o) { return o.name; }).join(", ") + ")"
        : "";
      var lineName = dishName + optionSuffix;

      window.BKCart.bump(compositeId, lineName, unitPrice, qty);
      confirmEl.classList.add("is-visible");
    });

    renderQty();
  });
})();
