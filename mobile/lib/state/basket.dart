import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/models.dart';

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
}

/// In-memory only for now — cleared on app restart. Persisting across
/// restarts (`shared_preferences`) is a Phase 4 item
/// (docs/mobile/FLUTTER_APP_PLAN.md), deliberately deferred until the
/// core add/checkout flow is proven out.
class BasketNotifier extends StateNotifier<BasketState> {
  BasketNotifier() : super(const BasketState());

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
