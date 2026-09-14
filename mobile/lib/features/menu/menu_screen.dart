import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/models.dart';
import '../../state/api_providers.dart';
import '../../state/basket.dart';
import '../../state/selection.dart';
import '../../theme/poster_tokens.dart';
import '../../util/money.dart';

/// Menu — category filters + dish list, matching the poster's content
/// (README §10.3 cards) but with a persistent "view basket" bar instead
/// of forcing a tab switch on every add (docs/mobile/FLUTTER_APP_PLAN.md
/// Phase 3 IA note — a native mini-basket pattern, not the web drawer).
class MenuScreen extends ConsumerWidget {
  const MenuScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final daysAsync = ref.watch(orderableDaysProvider);

    return ColoredBox(
      color: PosterColors.paper,
      child: SafeArea(
        child: daysAsync.when(
          data: (days) {
            if (days.isEmpty) {
              return const Center(child: Text('Nothing orderable right now.', style: PosterText.bodyLarge));
            }
            final selectedIso = ref.watch(selectedDayIsoProvider) ?? days.first.iso;
            return _MenuBody(days: days, selectedIso: selectedIso);
          },
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (err, _) => Center(child: Text('$err', style: PosterText.bodyDefault)),
        ),
      ),
    );
  }
}

class _MenuBody extends ConsumerWidget {
  const _MenuBody({required this.days, required this.selectedIso});

  final List<OrderableDay> days;
  final String selectedIso;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final availabilityAsync = ref.watch(availabilityProvider(selectedIso));
    final basket = ref.watch(basketProvider);

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            PosterSpace.pageSidePadding, 16, PosterSpace.pageSidePadding, 8,
          ),
          child: const Text('02 — MENU', style: PosterText.eyebrow),
        ),
        if (days.length > 1) _DayChips(days: days, selectedIso: selectedIso),
        Expanded(
          child: availabilityAsync.when(
            data: (availability) => _DishList(availability: availability),
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (err, _) => Center(child: Text('$err', style: PosterText.bodyDefault)),
          ),
        ),
        if (!basket.isEmpty) _BasketBar(basket: basket),
      ],
    );
  }
}

class _DayChips extends ConsumerWidget {
  const _DayChips({required this.days, required this.selectedIso});

  final List<OrderableDay> days;
  final String selectedIso;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return SizedBox(
      height: 44,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: PosterSpace.pageSidePadding),
        itemCount: days.length,
        separatorBuilder: (context, i) => const SizedBox(width: 8),
        itemBuilder: (context, i) {
          final day = days[i];
          final selected = day.iso == selectedIso;
          return ChoiceChip(
            label: Text(day.dow),
            selected: selected,
            onSelected: (_) => ref.read(selectedDayIsoProvider.notifier).state = day.iso,
            selectedColor: PosterColors.blue,
            labelStyle: TextStyle(color: selected ? PosterColors.white : PosterColors.navy, fontWeight: FontWeight.w800),
          );
        },
      ),
    );
  }
}

class _DishList extends ConsumerWidget {
  const _DishList({required this.availability});

  final DayAvailability availability;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selectedCategory = ref.watch(selectedCategoryProvider);
    final categoryNames = availability.categories.map((c) => c.name).toList();

    final visibleDishes = selectedCategory == 'all'
        ? availability.allDishes
        : availability.categories.where((c) => c.name == selectedCategory).expand((c) => c.dishes).toList();

    return Column(
      children: [
        SizedBox(
          height: 44,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: PosterSpace.pageSidePadding),
            children: [
              _CategoryChip(label: 'Everything', value: 'all', selectedValue: selectedCategory),
              const SizedBox(width: 8),
              for (final name in categoryNames) ...[
                _CategoryChip(label: name, value: name, selectedValue: selectedCategory),
                const SizedBox(width: 8),
              ],
            ],
          ),
        ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.fromLTRB(
              PosterSpace.pageSidePadding, 12, PosterSpace.pageSidePadding, PosterSpace.bottomPagePadding,
            ),
            itemCount: visibleDishes.length,
            itemBuilder: (context, i) => _DishCard(dish: visibleDishes[i]),
          ),
        ),
      ],
    );
  }
}

class _CategoryChip extends ConsumerWidget {
  const _CategoryChip({required this.label, required this.value, required this.selectedValue});

  final String label;
  final String value;
  final String selectedValue;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selected = value == selectedValue;
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => ref.read(selectedCategoryProvider.notifier).state = value,
      selectedColor: PosterColors.blue,
      labelStyle: TextStyle(color: selected ? PosterColors.white : PosterColors.navy, fontWeight: FontWeight.w800),
    );
  }
}

class _DishCard extends ConsumerWidget {
  const _DishCard({required this.dish});

  final Dish dish;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final basket = ref.watch(basketProvider);
    BasketLine? line;
    for (final candidate in basket.lines) {
      if (candidate.compositeKey == '${dish.id}:') {
        line = candidate;
        break;
      }
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: PosterColors.white,
        border: Border.all(color: PosterColors.border, width: 2),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Opacity(
        opacity: dish.soldOut ? 0.6 : 1,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            AspectRatio(
              aspectRatio: 1,
              child: dish.photoUrl.isNotEmpty
                  ? Image.network(dish.photoUrl, fit: BoxFit.cover)
                  : const ColoredBox(
                      color: PosterColors.bluePanel,
                      child: Icon(Icons.ramen_dining_rounded, color: PosterColors.blue, size: 32),
                    ),
            ),
            Expanded(
              flex: 2,
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (dish.category.isNotEmpty)
                      Text(dish.category.toUpperCase(), style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: PosterColors.blue)),
                    Text(dish.name.toUpperCase(), style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy)),
                    if (dish.shortDescription.isNotEmpty)
                      Text(dish.shortDescription, maxLines: 1, overflow: TextOverflow.ellipsis, style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
                    const SizedBox(height: 6),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(formatCents(dish.priceCents), style: PosterText.priceCard.copyWith(fontSize: 18, color: PosterColors.navy)),
                        if (dish.soldOut)
                          const Text('SOLD OUT', style: TextStyle(color: PosterColors.error, fontWeight: FontWeight.w900, fontSize: 11))
                        else if (line != null)
                          _QuantityStepper(compositeKey: line.compositeKey, quantity: line.quantity)
                        else
                          IconButton.filled(
                            onPressed: () => ref.read(basketProvider.notifier).addDish(dish),
                            icon: const Icon(Icons.add),
                            style: IconButton.styleFrom(backgroundColor: PosterColors.navy, foregroundColor: PosterColors.white),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuantityStepper extends ConsumerWidget {
  const _QuantityStepper({required this.compositeKey, required this.quantity});

  final String compositeKey;
  final int quantity;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(basketProvider.notifier);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          onPressed: () => notifier.setQuantity(compositeKey, quantity - 1),
          icon: const Icon(Icons.remove_circle_outline, size: 20),
        ),
        Text('$quantity', style: PosterText.button.copyWith(color: PosterColors.navy)),
        IconButton(
          onPressed: () => notifier.setQuantity(compositeKey, quantity + 1),
          icon: const Icon(Icons.add_circle_outline, size: 20),
        ),
      ],
    );
  }
}

class _BasketBar extends StatelessWidget {
  const _BasketBar({required this.basket});

  final BasketState basket;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Material(
        color: PosterColors.navy,
        child: InkWell(
          onTap: () => context.go('/basket'),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: PosterSpace.pageSidePadding, vertical: 14),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('${basket.itemCount} item${basket.itemCount == 1 ? '' : 's'}',
                    style: PosterText.button.copyWith(color: PosterColors.white)),
                Text(formatCents(basket.totalCents), style: PosterText.button.copyWith(color: PosterColors.gold)),
                const Icon(Icons.arrow_forward_rounded, color: PosterColors.white),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
