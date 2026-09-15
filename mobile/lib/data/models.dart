/// Plain Dart models for `public/api.py`'s JSON responses. Hand-written,
/// not code-generated (`json_serializable`/`freezed`) — the payload
/// shapes are small and stable enough that the build_runner step isn't
/// worth it yet; revisit if this file grows unwieldy.
///
/// Pruned to just the dish/option shapes 2026-09-15, when the app
/// became staff-only (see `docs/mobile/FLUTTER_APP_PLAN.md` Phase 7):
/// every other model here (orderable days, availability, checkout,
/// order status, account, reorder...) belonged to the customer-facing
/// screens that were removed. These three survive because the one
/// staff screen that still needs a dish-options picker (New assisted
/// order, `features/staff/assisted_order/`) shares the configurator
/// widget the old customer Menu screen used
/// (`shared/dish_option_sheet.dart`) rather than a second copy of it.
library;

class DishOptionValue {
  const DishOptionValue({required this.id, required this.name, required this.priceDeltaCents});

  factory DishOptionValue.fromJson(Map<String, dynamic> json) => DishOptionValue(
        id: json['id'] as int,
        name: json['name'] as String,
        priceDeltaCents: json['price_delta_cents'] as int,
      );

  final int id;
  final String name;
  final int priceDeltaCents;
}

class DishOption {
  const DishOption({required this.id, required this.name, required this.required, required this.values});

  factory DishOption.fromJson(Map<String, dynamic> json) => DishOption(
        id: json['id'] as int,
        name: json['name'] as String,
        required: json['required'] as bool,
        values: (json['values'] as List<dynamic>)
            .map((v) => DishOptionValue.fromJson(v as Map<String, dynamic>))
            .toList(),
      );

  final int id;
  final String name;
  final bool required;
  final List<DishOptionValue> values;
}

class Dish {
  const Dish({
    required this.id,
    required this.slug,
    required this.name,
    required this.shortDescription,
    required this.priceCents,
    required this.soldOut,
    required this.photoUrl,
    required this.portionLabel,
    required this.category,
    required this.options,
  });

  factory Dish.fromJson(Map<String, dynamic> json) => Dish(
        id: json['id'] as int,
        slug: json['slug'] as String,
        name: json['name'] as String,
        shortDescription: (json['short_description'] as String?) ?? '',
        priceCents: json['price_cents'] as int,
        soldOut: (json['sold_out'] as bool?) ?? false,
        photoUrl: (json['photo_url'] as String?) ?? '',
        portionLabel: (json['portion_label'] as String?) ?? '',
        category: (json['category'] as String?) ?? '',
        options: (json['options'] as List<dynamic>?)
                ?.map((o) => DishOption.fromJson(o as Map<String, dynamic>))
                .toList() ??
            const [],
      );

  final int id;
  final String slug;
  final String name;
  final String shortDescription;
  final int priceCents;
  final bool soldOut;
  final String photoUrl;
  final String portionLabel;
  final String category;
  final List<DishOption> options;

  bool get hasOptions => options.isNotEmpty;
}
