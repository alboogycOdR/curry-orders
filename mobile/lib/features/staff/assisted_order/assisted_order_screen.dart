import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../data/models.dart' as models;
import '../../../data/staff/staff_api.dart';
import '../../../state/api_providers.dart';
import '../../../theme/poster_tokens.dart';
import '../../../util/money.dart';
import '../../menu/dish_option_sheet.dart';
import '../staff_scaffold.dart';

/// New assisted order (§12.9, M9) — staff placing an order on behalf of a
/// phone/in-person/WhatsApp customer. Backend:
/// `GET/POST /api/v1/staff/orders/new/` (`staff/api_mobile_assisted_order.py`),
/// which runs the exact same `core.capacity.reserve()` §8.3 transaction
/// public checkout uses — this screen has no capacity logic of its own,
/// only a form over that same call. Web reference:
/// `staff/views.py::assisted_order_new` /
/// `templates/staff/assisted_order_form.html`.
///
/// No client-side basket provider here (that's the customer side's own
/// state) — the "current order" list below is this screen's own local
/// state, shaped directly like the POST body's `lines` array.

// ---------------------------------------------------------------- API models

class _OptionValue {
  const _OptionValue({
    required this.id,
    required this.name,
    required this.priceDeltaCents,
    required this.isAvailable,
  });

  factory _OptionValue.fromJson(Map<String, dynamic> json) => _OptionValue(
        id: json['id'] as int,
        name: json['name'] as String,
        priceDeltaCents: json['price_delta_cents'] as int,
        isAvailable: (json['is_available'] as bool?) ?? true,
      );

  final int id;
  final String name;
  final int priceDeltaCents;
  final bool isAvailable;
}

class _Option {
  const _Option({
    required this.id,
    required this.name,
    required this.required,
    required this.values,
  });

  factory _Option.fromJson(Map<String, dynamic> json) => _Option(
        id: json['id'] as int,
        name: json['name'] as String,
        required: json['required'] as bool,
        values: (json['values'] as List<dynamic>)
            .map((v) => _OptionValue.fromJson(v as Map<String, dynamic>))
            .toList(),
      );

  final int id;
  final String name;
  final bool required;
  final List<_OptionValue> values;
}

class _AssistedDish {
  const _AssistedDish({
    required this.id,
    required this.slug,
    required this.name,
    required this.shortDescription,
    required this.priceCents,
    required this.soldOut,
    required this.portionLabel,
    required this.category,
    required this.options,
  });

  factory _AssistedDish.fromJson(Map<String, dynamic> json) => _AssistedDish(
        id: json['id'] as int,
        slug: json['slug'] as String,
        name: json['name'] as String,
        shortDescription: (json['short_description'] as String?) ?? '',
        priceCents: json['price_cents'] as int,
        soldOut: (json['sold_out'] as bool?) ?? false,
        portionLabel: (json['portion_label'] as String?) ?? '',
        category: (json['category'] as String?) ?? '',
        options: (json['options'] as List<dynamic>)
            .map((o) => _Option.fromJson(o as Map<String, dynamic>))
            .toList(),
      );

  final int id;
  final String slug;
  final String name;
  final String shortDescription;
  final int priceCents;
  final bool soldOut;
  final String portionLabel;
  final String category;
  final List<_Option> options;

  bool get hasOptions => options.isNotEmpty;

  /// Adapted to `data/models.dart`'s own `Dish` shape so this screen can
  /// reuse the customer app's `showDishOptionSheet` unchanged, rather than
  /// building a second configurator. Unavailable option values are
  /// dropped first — same filter `public/api.py::availability` applies
  /// for the customer side.
  models.Dish toSharedDish() => models.Dish(
        id: id,
        slug: slug,
        name: name,
        shortDescription: shortDescription,
        priceCents: priceCents,
        soldOut: soldOut,
        photoUrl: '',
        portionLabel: portionLabel,
        category: category,
        options: [
          for (final option in options)
            models.DishOption(
              id: option.id,
              name: option.name,
              required: option.required,
              values: [
                for (final value in option.values)
                  if (value.isAvailable)
                    models.DishOptionValue(
                      id: value.id,
                      name: value.name,
                      priceDeltaCents: value.priceDeltaCents,
                    ),
              ],
            ),
        ],
      );
}

class _Slot {
  const _Slot({
    required this.id,
    required this.label,
    required this.occupying,
    required this.capacity,
    required this.full,
  });

  factory _Slot.fromJson(Map<String, dynamic> json) => _Slot(
        id: json['id'] as int,
        label: json['label'] as String,
        occupying: json['occupying'] as int,
        capacity: json['capacity'] as int,
        full: json['full'] as bool,
      );

  final int id;
  final String label;
  final int occupying;
  final int capacity;
  final bool full;
}

class _FormData {
  const _FormData({
    required this.date,
    required this.minDate,
    required this.maxDate,
    required this.dishes,
    required this.slots,
    required this.cashEnabled,
    required this.assistedAfterCutoffEnabled,
    required this.isToday,
    required this.requiresAfterCutoffReason,
  });

  factory _FormData.fromJson(Map<String, dynamic> json) => _FormData(
        date: DateTime.parse(json['date'] as String),
        minDate: DateTime.parse(json['min_date'] as String),
        maxDate: DateTime.parse(json['max_date'] as String),
        dishes: (json['dishes'] as List<dynamic>)
            .map((d) => _AssistedDish.fromJson(d as Map<String, dynamic>))
            .toList(),
        slots: (json['slots'] as List<dynamic>)
            .map((s) => _Slot.fromJson(s as Map<String, dynamic>))
            .toList(),
        cashEnabled: json['cash_enabled'] as bool,
        assistedAfterCutoffEnabled: json['assisted_after_cutoff_enabled'] as bool,
        isToday: json['is_today'] as bool,
        requiresAfterCutoffReason: json['requires_after_cutoff_reason'] as bool,
      );

  final DateTime date;
  final DateTime minDate;
  final DateTime maxDate;
  final List<_AssistedDish> dishes;
  final List<_Slot> slots;
  final bool cashEnabled;
  final bool assistedAfterCutoffEnabled;
  final bool isToday;
  final bool requiresAfterCutoffReason;
}

// ---------------------------------------------------------------- local order-line state

class _OrderLine {
  _OrderLine({
    required this.dishId,
    required this.dishName,
    required this.unitPriceCents,
    required this.optionValueIds,
    required this.optionsSummary,
  });

  final int dishId;
  final String dishName;
  final int unitPriceCents;
  final List<int> optionValueIds;
  final String optionsSummary;
  int quantity = 1;

  /// Same dish + same option picks merge into one line with a bumped
  /// quantity, rather than piling up duplicate rows.
  String get mergeKey => '$dishId:${optionValueIds.join(",")}';

  int get lineTotalCents => unitPriceCents * quantity;
}

String _isoDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-'
    '${d.day.toString().padLeft(2, '0')}';

const _sourceOptions = [
  ('phone', 'Phone'),
  ('in_person', 'In person'),
  ('whatsapp_assisted', 'WhatsApp'),
];

const _eftModeOptions = [
  ('hold', 'Awaiting EFT (default)'),
  ('payment_review', 'Customer says paid'),
  ('confirmed_prep', 'Staff saw the funds'),
];

class AssistedOrderScreen extends ConsumerStatefulWidget {
  const AssistedOrderScreen({super.key});

  @override
  ConsumerState<AssistedOrderScreen> createState() => _AssistedOrderScreenState();
}

class _AssistedOrderScreenState extends ConsumerState<AssistedOrderScreen> {
  final _nameController = TextEditingController();
  final _mobileController = TextEditingController();
  final _noteController = TextEditingController();
  final _afterCutoffReasonController = TextEditingController();
  final _eftConfirmReasonController = TextEditingController();

  bool _loadingForm = true;
  String? _loadError;
  _FormData? _form;
  DateTime? _date;

  final List<_OrderLine> _lines = [];
  int? _slotId;
  String _source = 'phone';
  String _paymentMethod = 'eft';
  String _eftMode = 'hold';

  bool _submitting = false;
  String? _submitError;
  Map<String, String> _fieldErrors = {};

  @override
  void initState() {
    super.initState();
    _loadForm();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _mobileController.dispose();
    _noteController.dispose();
    _afterCutoffReasonController.dispose();
    _eftConfirmReasonController.dispose();
    super.dispose();
  }

  Future<void> _loadForm({DateTime? date}) async {
    setState(() {
      _loadingForm = true;
      _loadError = null;
    });
    try {
      final dio = ref.read(apiClientProvider).dio;
      final resp = await dio.get<dynamic>(
        'staff/orders/new/',
        queryParameters: date == null ? null : {'date': _isoDate(date)},
      );
      final form = parseStaffJson(resp, (d) => _FormData.fromJson(d as Map<String, dynamic>));
      if (!mounted) return;
      setState(() {
        _form = form;
        _date = form.date;
        _loadingForm = false;
        // A new day's dishes/slots may not match what was picked before —
        // same as the web's own prev/next-day links, which reload the
        // whole form rather than carry a part-built order across dates.
        _lines.clear();
        _slotId = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loadError = "Couldn't load the form — check your connection and try again.";
        _loadingForm = false;
      });
    }
  }

  Future<void> _pickDate() async {
    final form = _form;
    final current = _date;
    if (form == null || current == null) return;
    final picked = await showDatePicker(
      context: context,
      initialDate: current,
      firstDate: form.minDate,
      lastDate: form.maxDate,
    );
    if (picked == null) return;
    await _loadForm(date: picked);
  }

  void _addBareDish(_AssistedDish dish) {
    setState(() {
      final existing = _lines.where((l) => l.mergeKey == '${dish.id}:').firstOrNull;
      if (existing != null) {
        existing.quantity += 1;
      } else {
        _lines.add(_OrderLine(
          dishId: dish.id,
          dishName: dish.name,
          unitPriceCents: dish.priceCents,
          optionValueIds: const [],
          optionsSummary: '',
        ));
      }
    });
  }

  Future<void> _addDishWithOptions(_AssistedDish dish) async {
    final selection = await showDishOptionSheet(context, dish.toSharedDish());
    if (selection == null || !mounted) return;
    setState(() {
      final key = '${dish.id}:${(List<int>.from(selection.optionValueIds)..sort()).join(",")}';
      final existing = _lines.where((l) => l.mergeKey == key).firstOrNull;
      if (existing != null) {
        existing.quantity += 1;
      } else {
        _lines.add(_OrderLine(
          dishId: dish.id,
          dishName: dish.name,
          unitPriceCents: selection.unitPriceCents,
          optionValueIds: selection.optionValueIds,
          optionsSummary: selection.summary,
        ));
      }
    });
  }

  void _setLineQuantity(_OrderLine line, int quantity) {
    setState(() {
      if (quantity <= 0) {
        _lines.remove(line);
      } else {
        line.quantity = quantity;
      }
    });
  }

  int get _totalCents => _lines.fold(0, (sum, l) => sum + l.lineTotalCents);

  bool get _canSubmit {
    final form = _form;
    if (form == null || _submitting) return false;
    final name = _nameController.text.trim();
    if (name.length < 2 || name.length > 80) return false;
    if (_mobileController.text.trim().isEmpty) return false;
    if (_lines.isEmpty) return false;
    if (_slotId == null) return false;
    if (form.requiresAfterCutoffReason && _afterCutoffReasonController.text.trim().isEmpty) {
      return false;
    }
    if (_paymentMethod == 'cash' && !form.cashEnabled) return false;
    if (_paymentMethod == 'eft' &&
        _eftMode == 'confirmed_prep' &&
        _eftConfirmReasonController.text.trim().isEmpty) {
      return false;
    }
    return true;
  }

  Future<void> _submit() async {
    final form = _form;
    if (form == null || !_canSubmit) return;
    setState(() {
      _submitting = true;
      _submitError = null;
      _fieldErrors = {};
    });
    try {
      final dio = ref.read(apiClientProvider).dio;
      final resp = await dio.post<dynamic>(
        'staff/orders/new/',
        data: {
          'date': _isoDate(_date ?? form.date),
          'customer_name': _nameController.text.trim(),
          'customer_mobile': _mobileController.text.trim(),
          'note': _noteController.text.trim(),
          'source': _source,
          'slot_id': _slotId,
          'after_cutoff_reason': _afterCutoffReasonController.text.trim().isEmpty
              ? null
              : _afterCutoffReasonController.text.trim(),
          'payment_method': _paymentMethod,
          'eft_mode': _paymentMethod == 'eft' ? _eftMode : null,
          'eft_confirm_reason': _eftConfirmReasonController.text.trim().isEmpty
              ? null
              : _eftConfirmReasonController.text.trim(),
          'lines': [
            for (final line in _lines)
              {
                'dish_id': line.dishId,
                'quantity': line.quantity,
                'option_value_ids': line.optionValueIds,
              },
          ],
        },
      );
      final status = resp.statusCode ?? 0;
      if (status >= 200 && status < 300) {
        final body = resp.data as Map<String, dynamic>;
        final orderNumber = body['order_number'] as String?;
        final warning = body['warning'] as String?;
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(warning ?? 'Order $orderNumber created.')),
        );
        context.go('/staff/inbox');
        return;
      }
      _applyErrorResponse(resp.data);
    } catch (e) {
      if (mounted) {
        setState(() {
          _submitError = "Couldn't reach the server — check your connection and try again.";
        });
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _applyErrorResponse(dynamic data) {
    if (data is! Map<String, dynamic>) {
      setState(() => _submitError = 'Something went wrong.');
      return;
    }
    final message = (data['message'] as String?) ?? 'Something went wrong.';
    final rawErrors = data['errors'];
    if (rawErrors is List && rawErrors.isNotEmpty) {
      final fieldErrors = <String, String>{};
      for (final entry in rawErrors) {
        if (entry is Map) {
          final field = entry['field']?.toString();
          final msg = entry['message']?.toString();
          if (field != null && msg != null) fieldErrors[field] = msg;
        }
      }
      setState(() {
        _fieldErrors = fieldErrors;
        _submitError = fieldErrors.isEmpty ? message : null;
      });
    } else {
      setState(() => _submitError = message);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StaffScaffold(
      title: 'New assisted order',
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loadingForm && _form == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_loadError != null && _form == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _loadError!,
                style: PosterText.bodyDefault.copyWith(color: PosterColors.error),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: () => _loadForm(), child: const Text('Retry')),
            ],
          ),
        ),
      );
    }
    final form = _form!;
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        PosterSpace.pageSidePadding, 16, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
      ),
      children: [
        _SectionTitle('Collection date'),
        OutlinedButton.icon(
          onPressed: _loadingForm ? null : _pickDate,
          icon: const Icon(Icons.calendar_today_rounded, size: 18),
          label: Text(_date == null ? '—' : _isoDate(_date!)),
        ),
        if (_loadingForm) const Padding(
          padding: EdgeInsets.only(top: 8),
          child: LinearProgressIndicator(),
        ),
        const SizedBox(height: 20),

        _SectionTitle('Dishes'),
        for (final dish in form.dishes) _DishRow(
          dish: dish,
          currentQuantity: _lines
              .where((l) => l.mergeKey == '${dish.id}:')
              .fold(0, (sum, l) => sum + l.quantity),
          onAdd: () => dish.hasOptions ? _addDishWithOptions(dish) : _addBareDish(dish),
          onSetQuantity: (q) {
            final existing = _lines.where((l) => l.mergeKey == '${dish.id}:').firstOrNull;
            if (existing != null) {
              _setLineQuantity(existing, q);
            } else if (q > 0) {
              _addBareDish(dish);
            }
          },
        ),

        const SizedBox(height: 20),
        _SectionTitle('Your order'),
        if (_lines.isEmpty)
          Text('No dishes added yet.', style: PosterText.bodyDefault.copyWith(color: PosterColors.muted))
        else
          for (final line in _lines) _OrderLineRow(
            line: line,
            onSetQuantity: (q) => _setLineQuantity(line, q),
          ),
        if (_fieldErrors['lines'] != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(_fieldErrors['lines']!, style: const TextStyle(color: PosterColors.error, fontSize: 12)),
          ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('Total', style: PosterText.button),
            Text(formatCents(_totalCents), style: PosterText.priceCard.copyWith(color: PosterColors.navy)),
          ],
        ),

        const SizedBox(height: 24),
        _SectionTitle('Customer'),
        TextField(
          controller: _nameController,
          decoration: InputDecoration(labelText: 'Full name', errorText: _fieldErrors['customer_name']),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _mobileController,
          keyboardType: TextInputType.phone,
          decoration: InputDecoration(labelText: 'Mobile number', errorText: _fieldErrors['customer_mobile']),
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _noteController,
          maxLength: 200,
          decoration: InputDecoration(labelText: 'Order note (optional)', errorText: _fieldErrors['note']),
        ),

        const SizedBox(height: 12),
        _SectionTitle('Order source'),
        RadioGroup<String>(
          groupValue: _source,
          onChanged: (v) => setState(() => _source = v ?? _source),
          child: Column(
            children: [
              for (final option in _sourceOptions)
                RadioListTile<String>(value: option.$1, dense: true, title: Text(option.$2)),
            ],
          ),
        ),
        if (_fieldErrors['source'] != null)
          Text(_fieldErrors['source']!, style: const TextStyle(color: PosterColors.error, fontSize: 12)),

        const SizedBox(height: 12),
        _SectionTitle('Collection slot'),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final slot in form.slots)
              ChoiceChip(
                label: Text('${slot.label} (${slot.occupying}/${slot.capacity})'),
                selected: _slotId == slot.id,
                onSelected: slot.full ? null : (selected) => setState(() => _slotId = selected ? slot.id : null),
              ),
          ],
        ),
        if (_fieldErrors['slot_id'] != null)
          Text(_fieldErrors['slot_id']!, style: const TextStyle(color: PosterColors.error, fontSize: 12)),

        if (form.requiresAfterCutoffReason) ...[
          const SizedBox(height: 12),
          TextField(
            controller: _afterCutoffReasonController,
            decoration: InputDecoration(
              labelText: 'After-cut-off reason',
              helperText: 'Required for a same-day assisted order',
              errorText: _fieldErrors['after_cutoff_reason'],
            ),
            onChanged: (_) => setState(() {}),
          ),
        ] else if (form.isToday && !form.assistedAfterCutoffEnabled)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              'Assisted-after-cutoff is disabled in Settings — a same-day order will be refused '
              'until it\'s turned on.',
              style: PosterText.bodyDefault.copyWith(color: PosterColors.error),
            ),
          ),

        const SizedBox(height: 24),
        _SectionTitle('Payment'),
        RadioGroup<String>(
          groupValue: _paymentMethod,
          onChanged: (v) => setState(() => _paymentMethod = v ?? _paymentMethod),
          child: Column(
            children: [
              const RadioListTile<String>(value: 'eft', dense: true, title: Text('EFT')),
              if (form.cashEnabled)
                const RadioListTile<String>(value: 'cash', dense: true, title: Text('Cash')),
            ],
          ),
        ),
        if (_fieldErrors['payment_method'] != null)
          Text(_fieldErrors['payment_method']!, style: const TextStyle(color: PosterColors.error, fontSize: 12)),

        if (_paymentMethod == 'eft') ...[
          const SizedBox(height: 12),
          Text('EFT status', style: PosterText.eyebrow.copyWith(color: PosterColors.blue)),
          RadioGroup<String>(
            groupValue: _eftMode,
            onChanged: (v) => setState(() => _eftMode = v ?? _eftMode),
            child: Column(
              children: [
                for (final option in _eftModeOptions)
                  RadioListTile<String>(value: option.$1, dense: true, title: Text(option.$2)),
              ],
            ),
          ),
          if (_eftMode == 'confirmed_prep') ...[
            const SizedBox(height: 8),
            TextField(
              controller: _eftConfirmReasonController,
              decoration: InputDecoration(
                labelText: 'Reason (required for "Staff saw the funds" — D-18)',
                errorText: _fieldErrors['eft_confirm_reason'],
              ),
              onChanged: (_) => setState(() {}),
            ),
          ],
        ],

        const SizedBox(height: 24),
        if (_submitError != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(_submitError!, style: const TextStyle(color: PosterColors.error)),
          ),
        ElevatedButton(
          style: ElevatedButton.styleFrom(
            backgroundColor: PosterColors.navy,
            foregroundColor: PosterColors.white,
            minimumSize: const Size.fromHeight(48),
          ),
          onPressed: _canSubmit ? _submit : null,
          child: _submitting
              ? const SizedBox(
                  height: 20, width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2, color: PosterColors.white),
                )
              : const Text('CREATE ORDER', style: PosterText.button),
        ),
      ],
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        text.toUpperCase(),
        style: PosterText.eyebrow.copyWith(color: PosterColors.navy),
      ),
    );
  }
}

class _DishRow extends StatelessWidget {
  const _DishRow({
    required this.dish,
    required this.currentQuantity,
    required this.onAdd,
    required this.onSetQuantity,
  });

  final _AssistedDish dish;
  final int currentQuantity;
  final VoidCallback onAdd;
  final ValueChanged<int> onSetQuantity;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: dish.soldOut ? 0.5 : 1,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(dish.name, style: PosterText.bodyLarge.copyWith(color: PosterColors.navy)),
                  Text(
                    dish.soldOut ? 'Sold out today' : formatCents(dish.priceCents),
                    style: PosterText.bodyDefault.copyWith(
                      color: dish.soldOut ? PosterColors.error : PosterColors.muted,
                    ),
                  ),
                ],
              ),
            ),
            if (dish.soldOut)
              const SizedBox.shrink()
            else if (dish.hasOptions)
              OutlinedButton(onPressed: onAdd, child: const Text('Add'))
            else
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  IconButton(
                    onPressed: currentQuantity > 0 ? () => onSetQuantity(currentQuantity - 1) : null,
                    icon: const Icon(Icons.remove_circle_outline, size: 20),
                  ),
                  Text('$currentQuantity', style: PosterText.button.copyWith(color: PosterColors.navy)),
                  IconButton(
                    onPressed: () => onSetQuantity(currentQuantity + 1),
                    icon: const Icon(Icons.add_circle_outline, size: 20),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _OrderLineRow extends StatelessWidget {
  const _OrderLineRow({required this.line, required this.onSetQuantity});

  final _OrderLine line;
  final ValueChanged<int> onSetQuantity;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(line.dishName, style: PosterText.bodyLarge.copyWith(color: PosterColors.navy)),
                if (line.optionsSummary.isNotEmpty)
                  Text(line.optionsSummary, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
              ],
            ),
          ),
          IconButton(
            onPressed: () => onSetQuantity(line.quantity - 1),
            icon: const Icon(Icons.remove_circle_outline, size: 20),
          ),
          Text('${line.quantity}', style: PosterText.button.copyWith(color: PosterColors.navy)),
          IconButton(
            onPressed: () => onSetQuantity(line.quantity + 1),
            icon: const Icon(Icons.add_circle_outline, size: 20),
          ),
          SizedBox(
            width: 64,
            child: Text(
              formatCents(line.lineTotalCents),
              textAlign: TextAlign.right,
              style: PosterText.bodyDefault.copyWith(color: PosterColors.navy),
            ),
          ),
        ],
      ),
    );
  }
}
