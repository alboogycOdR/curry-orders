// item-sheet.js — bottom-sheet item configurator (PR 4, KD-8).
//
// Reads `#menu-data` (emitted by views.order / views.basket as
// json_script from _menu_catalog_payload). Each catalog entry:
//   { id, slug, name, short_description, price_cents, portion_label,
//     photo_url, sold_out, options: [{id, name, required, values:[{id,name,price_delta_cents}]}] }
//
// Two modes (set on open):
//   add  — upsertLine into BKCart; button "Add · R{live}"
//   edit — updateLine for an existing line id; button "Update · R{live}"
//
// Usage (from order.js / basket.js):
//   window.BKItemSheet.open(itemId)         — add mode
//   window.BKItemSheet.openEdit(lineId, itemId) — edit mode (from Basket)
//
// Dispatches a custom event on close:
//   document.dispatchEvent(new CustomEvent('bkItemSheet:added', { detail: { line } }))
//   document.dispatchEvent(new CustomEvent('bkItemSheet:updated', { detail: { lineId } }))
(function () {
  "use strict";

  var _catalog = null; // lazy parsed from #menu-data

  function getCatalog() {
    if (_catalog) return _catalog;
    var el = document.getElementById("menu-data");
    if (!el) return [];
    try { _catalog = JSON.parse(el.textContent); } catch (e) { _catalog = []; }
    return _catalog;
  }

  function findItem(itemId) {
    var items = getCatalog();
    for (var i = 0; i < items.length; i++) {
      if (items[i].id === itemId) return items[i];
    }
    return null;
  }

  // ---------------------------------------------------------------- sheet elements (resolved once on DOMContentLoaded)

  var els = {};

  function resolveEls() {
    if (els.wrap) return;
    els.wrap        = document.getElementById("item-sheet");
    els.backdrop    = document.getElementById("is-backdrop");
    els.panel       = document.getElementById("is-panel");
    els.title       = document.getElementById("is-title");
    els.close       = document.getElementById("is-close");
    els.photoWrap   = document.getElementById("is-photo-wrap");
    els.photo       = document.getElementById("is-photo");
    els.price       = document.getElementById("is-price");
    els.portion     = document.getElementById("is-portion");
    els.desc        = document.getElementById("is-desc");
    els.heatGroup   = document.getElementById("is-group-heat");
    els.heatChips   = document.getElementById("is-heat-chips");
    els.extrasGroups = document.getElementById("is-extras-groups");
    els.notes       = document.getElementById("is-notes");
    els.notesCount  = document.getElementById("is-notes-count");
    els.qtyRow      = document.getElementById("is-qty-row");
    els.qtyCount    = document.getElementById("is-qty-count");
    els.qtyDec      = document.getElementById("is-qty-dec");
    els.qtyInc      = document.getElementById("is-qty-inc");
    els.addBtn      = document.getElementById("is-add-btn");
  }

  // ---------------------------------------------------------------- state

  var _mode = "add"; // "add" | "edit"
  var _editLineId = null;
  var _item = null;
  var _qty = 1;
  var _selections = {}; // optionId -> [valueId, ...]
  var _spiceGroupId = null; // the Spice option id (shown as "Heat")

  function _reset() {
    _mode = "add";
    _editLineId = null;
    _item = null;
    _qty = 1;
    _selections = {};
    _spiceGroupId = null;
  }

  // ---------------------------------------------------------------- rendering

  function _escape(s) {
    var d = document.createElement("div");
    d.textContent = String(s == null ? "" : s);
    return d.innerHTML;
  }

  function _computePrice() {
    if (!_item) return 0;
    var base = _item.price_cents;
    var delta = 0;
    (_item.options || []).forEach(function (opt) {
      var sel = _selections[opt.id] || [];
      (opt.values || []).forEach(function (v) {
        if (sel.indexOf(v.id) !== -1) delta += v.price_delta_cents;
      });
    });
    return base + delta;
  }

  function _updateAddBtn() {
    var price = _computePrice();
    var ready = true;
    // Heat required: must have a selection in the spice group
    if (_spiceGroupId !== null) {
      if (!_selections[_spiceGroupId] || !_selections[_spiceGroupId].length) {
        ready = false;
      }
    }
    els.addBtn.disabled = !ready;
    var label = _mode === "edit" ? "Update" : "Add";
    els.addBtn.textContent = label + " · " + window.BKCart.rands(price * _qty);
  }

  function _buildHeatChips(option) {
    var html = "";
    (option.values || []).forEach(function (v) {
      var isSel = (_selections[option.id] || []).indexOf(v.id) !== -1;
      html +=
        '<button type="button" class="is-chip' + (isSel ? " is-selected" : "") + '" ' +
        'data-opt-id="' + option.id + '" data-val-id="' + v.id + '">' +
        _escape(v.name) + "</button>";
    });
    els.heatChips.innerHTML = html;
    els.heatGroup.hidden = false;
  }

  function _buildExtrasGroups(options) {
    var html = "";
    options.forEach(function (opt) {
      if (opt.name === "Spice") return; // shown in Heat group
      var sels = _selections[opt.id] || [];
      html += '<div class="is-group" data-extra-group="' + opt.id + '">';
      html += '<div class="is-group-label">' + _escape(opt.name);
      if (!opt.required) html += ' <span class="is-group-req">Optional</span>';
      html += "</div>";
      html += '<div class="is-chips">';
      (opt.values || []).forEach(function (v) {
        var isSel = sels.indexOf(v.id) !== -1;
        var deltaText = v.price_delta_cents
          ? '<span class="is-chip-delta">' +
            (v.price_delta_cents > 0 ? "+" : "") +
            window.BKCart.rands(v.price_delta_cents) + "</span>"
          : "";
        html +=
          '<button type="button" class="is-chip' + (isSel ? " is-selected" : "") + '" ' +
          'data-opt-id="' + opt.id + '" data-val-id="' + v.id + '" ' +
          'data-required="' + (opt.required ? "1" : "0") + '">' +
          _escape(v.name) + deltaText + "</button>";
      });
      html += "</div></div>";
    });
    els.extrasGroups.innerHTML = html;
  }

  function _populate(item) {
    _item = item;

    // Title / photo / meta / desc
    els.title.textContent = item.name;
    if (item.photo_url) {
      els.photo.src = item.photo_url;
      els.photoWrap.classList.remove("is-placeholder");
      els.photoWrap.classList.add("has-photo");
    } else {
      els.photo.src = "";
      els.photoWrap.classList.add("is-placeholder");
      els.photoWrap.classList.remove("has-photo");
    }
    els.desc.textContent = item.short_description || "";
    els.portion.textContent = item.portion_label || "";

    // Options
    els.heatGroup.hidden = true;
    els.extrasGroups.innerHTML = "";
    _spiceGroupId = null;

    var options = item.options || [];

    // Default selection: first Spice value (Medium if present, else first)
    options.forEach(function (opt) {
      if (opt.name === "Spice") {
        _spiceGroupId = opt.id;
        if (!_selections[opt.id] || !_selections[opt.id].length) {
          var medium = null, first = null;
          (opt.values || []).forEach(function (v) {
            if (!first) first = v.id;
            if (v.name === "Medium") medium = v.id;
          });
          _selections[opt.id] = [medium || first];
        }
        _buildHeatChips(opt);
      }
    });
    _buildExtrasGroups(options);

    // Qty row — edit mode only
    if (_mode === "edit") {
      els.qtyRow.hidden = false;
      els.qtyCount.textContent = String(_qty);
      els.qtyDec.disabled = _qty <= 1;
      els.qtyInc.disabled = _qty >= 20;
    } else {
      els.qtyRow.hidden = true;
    }

    _updateAddBtn();
  }

  function _refreshPrice() {
    els.price.textContent = window.BKCart.rands(_computePrice());
    _updateAddBtn();
  }

  // ---------------------------------------------------------------- open / close

  function _openWith(item) {
    resolveEls();
    if (!els.wrap || !item) return;

    _populate(item);
    // Reset notes / count
    els.notes.value = "";
    els.notesCount.textContent = "0 / 80";

    els.wrap.hidden = false;
    document.body.classList.add("sheet-open");
    // Trap focus in panel
    els.panel.focus();
    _refreshPrice();
  }

  function open(itemId) {
    _reset();
    _mode = "add";
    _qty = 1;
    var item = findItem(itemId);
    if (!item) return;
    _openWith(item);
  }

  function openEdit(lineId, itemId) {
    _reset();
    _mode = "edit";
    _editLineId = lineId;
    // Pre-fill from existing cart line
    var lines = window.BKCart.getLines();
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].id === lineId) {
        _qty = lines[i].qty || 1;
        // Restore option selections from optionValueIds
        var item = findItem(itemId);
        if (item) {
          (item.options || []).forEach(function (opt) {
            var matching = (lines[i].optionValueIds || []).filter(function (vid) {
              return (opt.values || []).some(function (v) { return v.id === vid; });
            });
            if (matching.length) _selections[opt.id] = matching;
          });
        }
        if (lines[i].notes) {
          // Will be set after resolveEls
        }
        break;
      }
    }
    var it = findItem(itemId);
    if (!it) return;
    _openWith(it);
    // Set notes after DOM exists
    var existingLine = null;
    for (var j = 0; j < lines.length; j++) {
      if (lines[j].id === lineId) { existingLine = lines[j]; break; }
    }
    if (existingLine && existingLine.notes) {
      els.notes.value = existingLine.notes;
      els.notesCount.textContent = existingLine.notes.length + " / 80";
    }
  }

  function close() {
    resolveEls();
    if (!els.wrap) return;
    els.wrap.hidden = true;
    document.body.classList.remove("sheet-open");
  }

  // ---------------------------------------------------------------- chip click handler

  function _onChipClick(e) {
    var chip = e.target.closest(".is-chip[data-opt-id]");
    if (!chip) return;
    var optId = parseInt(chip.getAttribute("data-opt-id"), 10);
    var valId = parseInt(chip.getAttribute("data-val-id"), 10);
    var required = chip.getAttribute("data-required") === "1";
    var isHeat = (optId === _spiceGroupId);

    // For required / radio groups (including Heat): single select
    if (required || isHeat) {
      _selections[optId] = [valId];
      // Re-render only that group's chips
      var chips = (isHeat ? els.heatChips : chip.closest(".is-chips"))
                    .querySelectorAll(".is-chip[data-opt-id]");
      chips.forEach(function (c) {
        c.classList.toggle("is-selected", parseInt(c.getAttribute("data-val-id"), 10) === valId);
      });
    } else {
      // Optional/toggle: flip the chip
      var sels = _selections[optId] || [];
      var idx = sels.indexOf(valId);
      if (idx !== -1) sels.splice(idx, 1);
      else sels.push(valId);
      _selections[optId] = sels;
      chip.classList.toggle("is-selected", idx === -1);
    }
    _refreshPrice();
  }

  // ---------------------------------------------------------------- add / update

  function _buildLine() {
    var price = _computePrice();
    var allOptIds = [];
    var heatLabel = "";
    var extras = [];
    (_item.options || []).forEach(function (opt) {
      var sel = _selections[opt.id] || [];
      sel.forEach(function (vid) {
        allOptIds.push(vid);
        var v = (opt.values || []).find ? opt.values.find(function (vv) { return vv.id === vid; })
              : (function () {
                  for (var i = 0; i < opt.values.length; i++) {
                    if (opt.values[i].id === vid) return opt.values[i];
                  }
                })();
        if (!v) return;
        if (opt.name === "Spice") {
          heatLabel = v.name;
        } else if (v.price_delta_cents !== 0) {
          extras.push({ optionValueId: vid, name: v.name, deltaCents: v.price_delta_cents });
        }
      });
    });
    // Sort for stable id
    allOptIds.sort(function (a, b) { return a - b; });
    var id = allOptIds.length
      ? String(_item.id) + ":" + allOptIds.join(",")
      : String(_item.id);
    return {
      id: id,
      itemId: _item.id,
      name: _item.name,
      heat: heatLabel,
      extras: extras,
      notes: (els.notes.value || "").slice(0, 80),
      qty: _qty,
      unitPrice: price,
      lineTotal: price * _qty,
      photoUrl: _item.photo_url || "",
      optionValueIds: allOptIds,
    };
  }

  function _onAdd() {
    if (els.addBtn.disabled) return;
    var line = _buildLine();
    if (_mode === "edit") {
      // Remove old line, insert updated one
      window.BKCart.removeLine(_editLineId);
      window.BKCart.upsertLine(line);
      close();
      document.dispatchEvent(new CustomEvent("bkItemSheet:updated", { detail: { lineId: line.id } }));
    } else {
      window.BKCart.upsertLine(line);
      close();
      // Toast
      _showToast("Added · View basket");
      document.dispatchEvent(new CustomEvent("bkItemSheet:added", { detail: { line: line } }));
    }
  }

  // ---------------------------------------------------------------- qty (edit mode)

  function _setQty(n) {
    _qty = Math.max(1, Math.min(20, n));
    els.qtyCount.textContent = String(_qty);
    els.qtyDec.disabled = _qty <= 1;
    els.qtyInc.disabled = _qty >= 20;
    _updateAddBtn();
  }

  // ---------------------------------------------------------------- toast

  var _toastTimer = null;
  function _showToast(msg) {
    var toast = document.getElementById("is-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "is-toast";
      toast.className = "is-toast";
      document.body.appendChild(toast);
      var style = document.createElement("style");
      style.textContent = [
        ".is-toast{position:fixed;bottom:84px;left:50%;transform:translateX(-50%) translateY(8px);",
        "background:var(--color-text);color:var(--color-bg);",
        "padding:10px 20px;border-radius:var(--radius-pill,999px);",
        "font-size:14px;font-family:var(--font-ui,system-ui,sans-serif);",
        "opacity:0;transition:opacity 180ms ease,transform 180ms ease;",
        "pointer-events:none;white-space:nowrap;z-index:300;}",
        ".is-toast.is-visible{opacity:1;transform:translateX(-50%) translateY(0);}",
      ].join("");
      document.head.appendChild(style);
    }
    toast.textContent = msg;
    if (_toastTimer) clearTimeout(_toastTimer);
    requestAnimationFrame(function () {
      toast.classList.add("is-visible");
      _toastTimer = setTimeout(function () { toast.classList.remove("is-visible"); }, 2200);
    });
  }

  // ---------------------------------------------------------------- wiring (DOMContentLoaded)

  document.addEventListener("DOMContentLoaded", function () {
    resolveEls();
    if (!els.wrap) return;

    els.backdrop.addEventListener("click", close);
    els.close.addEventListener("click", close);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !els.wrap.hidden) close();
    });

    els.wrap.addEventListener("click", _onChipClick);
    els.addBtn.addEventListener("click", _onAdd);

    els.notes.addEventListener("input", function () {
      var len = els.notes.value.length;
      els.notesCount.textContent = len + " / 80";
      _updateAddBtn();
    });

    els.qtyDec.addEventListener("click", function () { _setQty(_qty - 1); });
    els.qtyInc.addEventListener("click", function () { _setQty(_qty + 1); });
  });

  // ---------------------------------------------------------------- public API

  window.BKItemSheet = {
    open:     open,
    openEdit: openEdit,
    close:    close,
  };
})();
