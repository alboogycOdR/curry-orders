import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/models.dart';

const _prefsKey = 'roti_connect.basket.v1';

/// One basket line. `compositeKey` (dish + chosen option values) is how
/// "add the same dish+options again" becomes "+1 quantity" instead of a
/// duplicate line — same rule the web cart (`static/js/cart.js`) uses.
class BasketLine {
  const BasketLine({
    required this.dishId,
    required this.name,
    required this.unitPriceCents,
    this.optionValueIds = const [],
    this.optionsSummary = '',
    this.quantity = 1,
    this.kitchenNote = '',
  });

  final int dishId;
  final String name;
  final int unitPriceCents;
  final List<int> optionValueIds;
  final String optionsSummary;
  final int quantity;
  final String kitchenNote;

  int get lineTotalCents => unitPriceCents * quantity;

  String get compositeKey => '$dishId:${optionValueIds.join(',')}';

  BasketLine copyWith({int? quantity, String? kitchenNote}) => BasketLine(
        dishId: dishId,
        name: name,
        unitPriceCents: unitPriceCents,
        optionValueIds: optionValueIds,
        optionsSummary: optionsSummary,
        quantity: quantity ?? this.quantity,
        kitchenNote: kitchenNote ?? this.kitchenNote,
      );

  Map<String, dynamic> toJson() => {
        'dishId': dishId,
        'name': name,
        'unitPriceCents': unitPriceCents,
        'optionValueIds': optionValueIds,
        'optionsSummary': optionsSummary,
        'quantity': quantity,
        'kitchenNote': kitchenNote,
      };

  factory BasketLine.fromJson(Map<String, dynamic> json) => BasketLine(
        dishId: json['dishId'] as int,
        name: json['name'] as String,
        unitPriceCents: json['unitPriceCents'] as int,
        optionValueIds: (json['optionValueIds'] as List<dynamic>).cast<int>(),
        optionsSummary: json['optionsSummary'] as String,
        quantity: json['quantity'] as int,
        kitchenNote: json['kitchenNote'] as String,
      );
}

class BasketState {
  const BasketState({this.lines = const [], this.collectionDateIso, this.slotId});

  final List<BasketLine> lines;
  final String? collectionDateIso;
  final int? slotId;

  int get itemCount => lines.fold(0, (sum, l) => sum + l.quantity);
  int get totalCents => lines.fold(0, (sum, l) => sum + l.lineTotalCents);
  bool get isEmpty => lines.isEmpty;
  bool get hasCollectionChoice => collectionDateIso != null && slotId != null;

  BasketState _copyWith({List<BasketLine>? lines, String? collectionDateIso, int? slotId}) =>
      BasketState(
        lines: lines ?? this.lines,
        collectionDateIso: collectionDateIso ?? this.collectionDateIso,
        slotId: slotId ?? this.slotId,
      );

  Map<String, dynamic> toJson() => {
        'lines': lines.map((l) => l.toJson()).toList(),
        'collectionDateIso': collectionDateIso,
        'slotId': slotId,
      };

  factory BasketState.fromJson(Map<String, dynamic> json) => BasketState(
        lines: (json['lines'] as List<dynamic>)
            .map((l) => BasketLine.fromJson(l as Map<String, dynamic>))
            .toList(),
        collectionDateIso: json['collectionDateIso'] as String?,
        slotId: json['slotId'] as int?,
      );
}

/// Persisted to `shared_preferences` after every mutation and restored
/// at construction — the cart survives an app restart (matching the
/// web's own `localStorage` cart). Load is async (`SharedPreferences` is
/// a platform channel call) so the very first frame briefly shows an
/// empty basket before `_restore()` resolves; that's an acceptable
/// startup flash rather than blocking app launch on it.
class BasketNotifier extends StateNotifier<BasketState> {
  BasketNotifier() : super(const BasketState()) {
    _restore();
  }

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefsKey);
    if (raw == null) return;
    try {
      state = BasketState.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      // Corrupt/old-shape data (e.g. a future schema change) — start
      // fresh rather than crash the app on launch.
      await prefs.remove(_prefsKey);
    }
  }

  Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, jsonEncode(state.toJson()));
  }

  // Persist on every state change in one place rather than after each
  // mutation method below — `state =` already routes through here.
  @override
  set state(BasketState value) {
    super.state = value;
    _persist();
  }

  void addDish(Dish dish, {List<int> optionValueIds = const [], String optionsSummary = '', int? priceCentsOverride}) {
    final unitPrice = priceCentsOverride ?? dish.priceCents;
    final key = '${dish.id}:${optionValueIds.join(',')}';
    final index = state.lines.indexWhere((l) => l.compositeKey == key);
    final updated = [...state.lines];
    if (index >= 0) {
      updated[index] = updated[index].copyWith(quantity: updated[index].quantity + 1);
    } else {
      updated.add(BasketLine(
        dishId: dish.id,
        name: dish.name,
        unitPriceCents: unitPrice,
        optionValueIds: optionValueIds,
        optionsSummary: optionsSummary,
      ));
    }
    state = state._copyWith(lines: updated);
  }

  /// Adds a line with an explicit quantity (merging into any existing
  /// line at the same composite key by *summing* quantities, not the
  /// "+1 per tap" behaviour [addDish] uses) — for reorder, which hands
  /// back a whole quantity per dish+options combination at once rather
  /// than one tap at a time.
  void addLine({
    required int dishId,
    required String name,
    required int unitPriceCents,
    List<int> optionValueIds = const [],
    String optionsSummary = '',
    required int quantity,
  }) {
    final key = '$dishId:${optionValueIds.join(',')}';
    final index = state.lines.indexWhere((l) => l.compositeKey == key);
    final updated = [...state.lines];
    if (index >= 0) {
      updated[index] = updated[index].copyWith(quantity: updated[index].quantity + quantity);
    } else {
      updated.add(BasketLine(
        dishId: dishId,
        name: name,
        unitPriceCents: unitPriceCents,
        optionValueIds: optionValueIds,
        optionsSummary: optionsSummary,
        quantity: quantity,
      ));
    }
    state = state._copyWith(lines: updated);
  }

  void setQuantity(String compositeKey, int quantity) {
    if (quantity <= 0) {
      state = state._copyWith(lines: state.lines.where((l) => l.compositeKey != compositeKey).toList());
      return;
    }
    state = state._copyWith(
      lines: [
        for (final line in state.lines)
          if (line.compositeKey == compositeKey) line.copyWith(quantity: quantity) else line,
      ],
    );
  }

  void setCollection(String dateIso, int slotId) {
    state = state._copyWith(collectionDateIso: dateIso, slotId: slotId);
  }

  void clear() {
    state = const BasketState();
  }
}

final basketProvider = StateNotifierProvider<BasketNotifier, BasketState>((ref) => BasketNotifier());
