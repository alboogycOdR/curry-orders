import 'package:flutter/material.dart';

import '../../data/models.dart';
import '../../theme/poster_tokens.dart';
import '../../util/money.dart';

/// Result of the configurator: which `DishOptionValue` ids were picked,
/// a display summary ("Hot, Extra cheese"), and the resulting unit price
/// (dish base price + every picked value's `price_delta_cents`).
class DishSelection {
  const DishSelection({required this.optionValueIds, required this.summary, required this.unitPriceCents});

  final List<int> optionValueIds;
  final String summary;
  final int unitPriceCents;
}

/// Bottom sheet for a dish with `DishOption`s (e.g. Spice, Extras) —
/// closes the gap flagged in docs/mobile/FLUTTER_APP_PLAN.md Phase 3:
/// previously a dish with required options could only be added at base
/// price with no way to actually choose them. One radio group per
/// *required* option (exactly one value, matching `core.capacity`'s own
/// checkout validation — a required option with nothing chosen would be
/// rejected server-side anyway), a checkbox per *optional* one (any
/// number, `Extra cheese`-style add-ons).
Future<DishSelection?> showDishOptionSheet(BuildContext context, Dish dish) {
  return showModalBottomSheet<DishSelection>(
    context: context,
    isScrollControlled: true,
    backgroundColor: PosterColors.paper,
    builder: (context) => _DishOptionSheet(dish: dish),
  );
}

class _DishOptionSheet extends StatefulWidget {
  const _DishOptionSheet({required this.dish});

  final Dish dish;

  @override
  State<_DishOptionSheet> createState() => _DishOptionSheetState();
}

class _DishOptionSheetState extends State<_DishOptionSheet> {
  // optionId -> chosen valueId, for required (single-choice) options.
  final Map<int, int> _requiredChoice = {};
  // valueId set for optional (multi-choice) options.
  final Set<int> _optionalChoices = {};

  @override
  void initState() {
    super.initState();
    for (final option in widget.dish.options) {
      if (option.required && option.values.isNotEmpty) {
        _requiredChoice[option.id] = option.values.first.id;
      }
    }
  }

  bool get _allRequiredChosen =>
      widget.dish.options.where((o) => o.required).every((o) => _requiredChoice.containsKey(o.id));

  int get _unitPriceCents {
    var total = widget.dish.priceCents;
    for (final option in widget.dish.options) {
      for (final value in option.values) {
        final chosen = option.required
            ? _requiredChoice[option.id] == value.id
            : _optionalChoices.contains(value.id);
        if (chosen) total += value.priceDeltaCents;
      }
    }
    return total;
  }

  String get _summary {
    final names = <String>[];
    for (final option in widget.dish.options) {
      for (final value in option.values) {
        final chosen = option.required
            ? _requiredChoice[option.id] == value.id
            : _optionalChoices.contains(value.id);
        if (chosen) names.add(value.name);
      }
    }
    return names.join(', ');
  }

  List<int> get _selectedValueIds {
    final ids = <int>[..._requiredChoice.values, ..._optionalChoices];
    ids.sort();
    return ids;
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
        child: DraggableScrollableSheet(
          initialChildSize: 0.6,
          maxChildSize: 0.9,
          expand: false,
          builder: (context, scrollController) => ListView(
            controller: scrollController,
            padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
            children: [
              Text(widget.dish.name.toUpperCase(), style: PosterText.cardTitle.copyWith(color: PosterColors.navy)),
              const SizedBox(height: 16),
              for (final option in widget.dish.options) _OptionGroup(
                option: option,
                requiredChoice: _requiredChoice[option.id],
                optionalChoices: _optionalChoices,
                onRequiredChanged: (valueId) => setState(() => _requiredChoice[option.id] = valueId),
                onOptionalToggled: (valueId, selected) => setState(() {
                  if (selected) {
                    _optionalChoices.add(valueId);
                  } else {
                    _optionalChoices.remove(valueId);
                  }
                }),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _allRequiredChosen
                    ? () => Navigator.of(context).pop(
                          DishSelection(
                            optionValueIds: _selectedValueIds,
                            summary: _summary,
                            unitPriceCents: _unitPriceCents,
                          ),
                        )
                    : null,
                child: Text('ADD — ${formatCents(_unitPriceCents)}'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _OptionGroup extends StatelessWidget {
  const _OptionGroup({
    required this.option,
    required this.requiredChoice,
    required this.optionalChoices,
    required this.onRequiredChanged,
    required this.onOptionalToggled,
  });

  final DishOption option;
  final int? requiredChoice;
  final Set<int> optionalChoices;
  final ValueChanged<int> onRequiredChanged;
  final void Function(int valueId, bool selected) onOptionalToggled;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            option.required ? option.name.toUpperCase() : '${option.name.toUpperCase()} (OPTIONAL)',
            style: PosterText.eyebrow.copyWith(color: PosterColors.blue),
          ),
          if (option.required)
            RadioGroup<int>(
              groupValue: requiredChoice,
              onChanged: (v) => onRequiredChanged(v!),
              child: Column(
                children: [
                  for (final value in option.values)
                    RadioListTile<int>(
                      value: value.id,
                      dense: true,
                      title: Text(value.priceDeltaCents == 0
                          ? value.name
                          : '${value.name} (+${formatCents(value.priceDeltaCents)})'),
                    ),
                ],
              ),
            )
          else
            for (final value in option.values)
              CheckboxListTile(
                dense: true,
                value: optionalChoices.contains(value.id),
                onChanged: (v) => onOptionalToggled(value.id, v ?? false),
                title: Text(value.priceDeltaCents == 0
                    ? value.name
                    : '${value.name} (+${formatCents(value.priceDeltaCents)})'),
                controlAffinity: ListTileControlAffinity.leading,
              ),
        ],
      ),
    );
  }
}
