/// Plain Dart models for `public/api.py`'s JSON responses. Hand-written,
/// not code-generated (`json_serializable`/`freezed`) — the payload
/// shapes are small and stable enough that the build_runner step isn't
/// worth it yet; revisit if this file grows unwieldy.
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

/// `GET /api/v1/featured/`'s "this week's special" hero dish — the
/// poster web home page's own hero card (`public.views.home`'s
/// `featured`), added to the app 2026-09-15 after Home shipped with no
/// way to show it at all. Deliberately a separate, smaller model from
/// [Dish] rather than reusing it: no `soldOut`/`options` here (Home
/// only ever shows this as a teaser pointing at Menu, never lets you
/// add it to the basket directly, so those fields don't apply).
class FeaturedDish {
  const FeaturedDish({
    required this.slug,
    required this.name,
    required this.shortDescription,
    required this.priceCents,
    required this.photoUrl,
    required this.portionLabel,
  });

  factory FeaturedDish.fromJson(Map<String, dynamic> json) => FeaturedDish(
        slug: json['slug'] as String,
        name: json['name'] as String,
        shortDescription: (json['short_description'] as String?) ?? '',
        priceCents: json['price_cents'] as int,
        photoUrl: (json['photo_url'] as String?) ?? '',
        portionLabel: (json['portion_label'] as String?) ?? '',
      );

  final String slug;
  final String name;
  final String shortDescription;
  final int priceCents;
  final String photoUrl;
  final String portionLabel;
}

/// One entry from `GET /api/v1/days/` — an actually-orderable date (open
/// + before cutoff), not just "in horizon". See that endpoint's own
/// docstring for why `DayAvailability`'s date param alone isn't enough.
class OrderableDay {
  const OrderableDay({
    required this.index,
    required this.iso,
    required this.dow,
    required this.dom,
    required this.long,
  });

  factory OrderableDay.fromJson(Map<String, dynamic> json) => OrderableDay(
        index: json['index'] as int,
        iso: json['iso'] as String,
        dow: json['dow'] as String,
        dom: json['dom'] as int,
        long: json['long'] as String,
      );

  final int index;
  final String iso; // yyyy-mm-dd
  final String dow; // "Today" or e.g. "Fri"
  final int dom;
  final String long; // e.g. "today, Fri 19 Sep"
}

class MenuCategory {
  const MenuCategory({required this.name, required this.portionLabel, required this.dishes});

  factory MenuCategory.fromJson(Map<String, dynamic> json) => MenuCategory(
        name: json['name'] as String,
        portionLabel: (json['portion_label'] as String?) ?? '',
        dishes: (json['dishes'] as List<dynamic>)
            .map((d) => Dish.fromJson(d as Map<String, dynamic>))
            .toList(),
      );

  final String name;
  final String portionLabel;
  final List<Dish> dishes;
}

class SlotInfo {
  const SlotInfo({required this.id, required this.label, required this.full});

  factory SlotInfo.fromJson(Map<String, dynamic> json) => SlotInfo(
        id: json['id'] as int,
        label: json['label'] as String,
        full: json['full'] as bool,
      );

  final int id;
  final String label;
  final bool full;
}

/// `GET /api/v1/availability/?date=` — one trading day's dishes + slots.
class DayAvailability {
  const DayAvailability({required this.date, required this.categories, required this.slots});

  factory DayAvailability.fromJson(Map<String, dynamic> json) => DayAvailability(
        date: json['date'] as String,
        categories: (json['categories'] as List<dynamic>)
            .map((c) => MenuCategory.fromJson(c as Map<String, dynamic>))
            .toList(),
        slots: (json['slots'] as List<dynamic>)
            .map((s) => SlotInfo.fromJson(s as Map<String, dynamic>))
            .toList(),
      );

  final String date; // ISO yyyy-mm-dd
  final List<MenuCategory> categories;
  final List<SlotInfo> slots;

  List<Dish> get allDishes => categories.expand((c) => c.dishes).toList();
}

class StepInfo {
  const StepInfo({required this.label, required this.filled, required this.active});

  factory StepInfo.fromJson(Map<String, dynamic> json) => StepInfo(
        label: json['label'] as String,
        filled: json['filled'] as bool,
        active: json['active'] as bool,
      );

  final String label;
  final bool filled;
  final bool active;
}

class OrderLineDetail {
  const OrderLineDetail({
    required this.dishName,
    required this.unitPriceCents,
    required this.quantity,
    required this.lineTotalCents,
    required this.kitchenNote,
  });

  factory OrderLineDetail.fromJson(Map<String, dynamic> json) => OrderLineDetail(
        dishName: json['dish_name'] as String,
        unitPriceCents: json['unit_price_cents'] as int,
        quantity: json['quantity'] as int,
        lineTotalCents: json['line_total_cents'] as int,
        kitchenNote: (json['kitchen_note'] as String?) ?? '',
      );

  final String dishName;
  final int unitPriceCents;
  final int quantity;
  final int lineTotalCents;
  final String kitchenNote;
}

class EftDetail {
  const EftDetail({
    required this.bankName,
    required this.accountName,
    required this.accountNumber,
    required this.branchCode,
    required this.accountType,
    required this.reference,
    required this.amountCents,
    required this.holdExpiresAt,
    required this.proofAlreadyUploaded,
  });

  factory EftDetail.fromJson(Map<String, dynamic> json) => EftDetail(
        bankName: (json['bank_name'] as String?) ?? '',
        accountName: (json['account_name'] as String?) ?? '',
        accountNumber: (json['account_number'] as String?) ?? '',
        branchCode: (json['branch_code'] as String?) ?? '',
        accountType: (json['account_type'] as String?) ?? '',
        reference: json['reference'] as String,
        amountCents: json['amount_cents'] as int,
        holdExpiresAt: json['hold_expires_at'] as String?,
        proofAlreadyUploaded: json['proof_already_uploaded'] as bool,
      );

  final String bankName;
  final String accountName;
  final String accountNumber;
  final String branchCode;
  final String accountType;
  final String reference;
  final int amountCents;
  final String? holdExpiresAt; // ISO datetime
  final bool proofAlreadyUploaded;
}

/// `GET /api/v1/orders/<token>/` — full order detail.
class OrderDetail {
  const OrderDetail({
    required this.orderNumber,
    required this.publicToken,
    required this.status,
    required this.statusCopy,
    required this.stepData,
    required this.isTerminal,
    required this.canReorder,
    required this.paymentMethod,
    required this.collectionMethod,
    required this.collectionDate,
    required this.collectionSlotLabel,
    required this.totalCents,
    required this.note,
    required this.lines,
    required this.collectionAddressLine,
    required this.collectionInstructions,
    required this.eft,
  });

  factory OrderDetail.fromJson(Map<String, dynamic> json) => OrderDetail(
        orderNumber: json['order_number'] as String,
        publicToken: json['public_token'] as String,
        status: json['status'] as String,
        statusCopy: json['status_copy'] as String,
        stepData: (json['step_data'] as List<dynamic>?)
            ?.map((s) => StepInfo.fromJson(s as Map<String, dynamic>))
            .toList(),
        isTerminal: json['is_terminal'] as bool,
        canReorder: json['can_reorder'] as bool,
        paymentMethod: json['payment_method'] as String,
        collectionMethod: json['collection_method'] as String,
        collectionDate: json['collection_date'] as String?,
        collectionSlotLabel: json['collection_slot_label'] as String?,
        totalCents: json['total_cents'] as int,
        note: (json['note'] as String?) ?? '',
        lines: (json['lines'] as List<dynamic>)
            .map((l) => OrderLineDetail.fromJson(l as Map<String, dynamic>))
            .toList(),
        collectionAddressLine: json['collection_address_line'] as String?,
        collectionInstructions: json['collection_instructions'] as String?,
        eft: json['eft'] != null ? EftDetail.fromJson(json['eft'] as Map<String, dynamic>) : null,
      );

  final String orderNumber;
  final String publicToken;
  final String status;
  final String statusCopy;
  final List<StepInfo>? stepData; // null for terminal statuses
  final bool isTerminal;
  final bool canReorder;
  final String paymentMethod;
  final String collectionMethod;
  final String? collectionDate;
  final String? collectionSlotLabel;
  final int totalCents;
  final String note;
  final List<OrderLineDetail> lines;
  final String? collectionAddressLine;
  final String? collectionInstructions;
  final EftDetail? eft;
}

/// Lighter entry from `GET /api/v1/account/orders/` — order history list.
class OrderSummary {
  const OrderSummary({
    required this.orderNumber,
    required this.publicToken,
    required this.status,
    required this.statusCopy,
    required this.totalCents,
    required this.createdAt,
  });

  factory OrderSummary.fromJson(Map<String, dynamic> json) => OrderSummary(
        orderNumber: json['order_number'] as String,
        publicToken: json['public_token'] as String,
        status: json['status'] as String,
        statusCopy: json['status_copy'] as String,
        totalCents: json['total_cents'] as int,
        createdAt: json['created_at'] as String,
      );

  final String orderNumber;
  final String publicToken;
  final String status;
  final String statusCopy;
  final int totalCents;
  final String createdAt; // ISO datetime
}

/// One line from `GET /api/v1/orders/<token>/reorder/` — a dish from a
/// past collected order, at today's price, with its options
/// best-effort re-matched against the dish's current option set.
class ReorderLine {
  const ReorderLine({
    required this.dishId,
    required this.dishName,
    required this.quantity,
    required this.optionValueIds,
    required this.optionsSummary,
    required this.unitPriceCents,
  });

  factory ReorderLine.fromJson(Map<String, dynamic> json) => ReorderLine(
        dishId: json['dish_id'] as int,
        dishName: json['dish_name'] as String,
        quantity: json['quantity'] as int,
        optionValueIds: (json['option_value_ids'] as List<dynamic>).cast<int>(),
        optionsSummary: (json['options_summary'] as String?) ?? '',
        unitPriceCents: json['unit_price_cents'] as int,
      );

  final int dishId;
  final String dishName;
  final int quantity;
  final List<int> optionValueIds;
  final String optionsSummary;
  final int unitPriceCents;
}

class ReorderResult {
  const ReorderResult({required this.lines, required this.droppedDishNames});

  factory ReorderResult.fromJson(Map<String, dynamic> json) => ReorderResult(
        lines: (json['lines'] as List<dynamic>)
            .map((l) => ReorderLine.fromJson(l as Map<String, dynamic>))
            .toList(),
        droppedDishNames: (json['dropped_dish_names'] as List<dynamic>).cast<String>(),
      );

  final List<ReorderLine> lines;
  final List<String> droppedDishNames;
}

class LastOrderRef {
  const LastOrderRef({required this.orderNumber, required this.publicToken});

  factory LastOrderRef.fromJson(Map<String, dynamic> json) => LastOrderRef(
        orderNumber: json['order_number'] as String,
        publicToken: json['public_token'] as String,
      );

  final String orderNumber;
  final String publicToken;
}

class CustomerAccount {
  const CustomerAccount({required this.fullName, required this.mobileE164, required this.lastOrder});

  factory CustomerAccount.fromJson(Map<String, dynamic> json) => CustomerAccount(
        fullName: json['full_name'] as String,
        mobileE164: json['mobile_e164'] as String,
        lastOrder: json['last_order'] != null
            ? LastOrderRef.fromJson(json['last_order'] as Map<String, dynamic>)
            : null,
      );

  final String fullName;
  final String mobileE164;
  final LastOrderRef? lastOrder;
}
