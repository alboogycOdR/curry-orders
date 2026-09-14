import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/models.dart';
import '../../state/api_providers.dart';
import '../../state/basket.dart';
import '../../state/selection.dart';
import '../../theme/poster_tokens.dart';
import '../../util/money.dart';

/// Basket — its own screen (a native tab, not the poster web build's
/// right-sliding drawer; see docs/mobile/FLUTTER_APP_PLAN.md Phase 3 IA
/// note on why a drawer has no clean native equivalent here). Lines +
/// day/slot picker + Continue, same content the web Basket page covers.
class BasketScreen extends ConsumerWidget {
  const BasketScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final basket = ref.watch(basketProvider);

    return ColoredBox(
      color: PosterColors.paper,
      child: SafeArea(
        child: basket.isEmpty ? const _EmptyBasket() : _BasketBody(basket: basket),
      ),
    );
  }
}

class _EmptyBasket extends StatelessWidget {
  const _EmptyBasket();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.shopping_bag_outlined, size: 48, color: PosterColors.muted),
          const SizedBox(height: 12),
          const Text('Your basket is empty.', style: PosterText.bodyLarge),
          const SizedBox(height: 16),
          ElevatedButton(onPressed: () => context.go('/menu'), child: const Text('BROWSE THE MENU')),
        ],
      ),
    );
  }
}

class _BasketBody extends ConsumerWidget {
  const _BasketBody({required this.basket});

  final BasketState basket;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final daysAsync = ref.watch(orderableDaysProvider);

    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
            children: [
              const Text('YOUR BASKET', style: PosterText.eyebrow),
              const SizedBox(height: 12),
              for (final line in basket.lines) _BasketLineRow(line: line),
              const SizedBox(height: 20),
              const Text('COLLECTION', style: PosterText.eyebrow),
              const SizedBox(height: 12),
              daysAsync.when(
                data: (days) => _CollectionPicker(days: days),
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (err, _) => Text('$err', style: PosterText.bodyDefault),
              ),
            ],
          ),
        ),
        _CheckoutFooter(basket: basket),
      ],
    );
  }
}

class _BasketLineRow extends ConsumerWidget {
  const _BasketLineRow({required this.line});

  final BasketLine line;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(basketProvider.notifier);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: PosterColors.white, borderRadius: BorderRadius.circular(5)),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(line.name, style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy)),
                Text(formatCents(line.unitPriceCents), style: PosterText.bodyDefault.copyWith(color: PosterColors.muted)),
              ],
            ),
          ),
          IconButton(
            onPressed: () => notifier.setQuantity(line.compositeKey, line.quantity - 1),
            icon: const Icon(Icons.remove_circle_outline),
          ),
          Text('${line.quantity}', style: PosterText.button.copyWith(color: PosterColors.navy)),
          IconButton(
            onPressed: () => notifier.setQuantity(line.compositeKey, line.quantity + 1),
            icon: const Icon(Icons.add_circle_outline),
          ),
          SizedBox(
            width: 64,
            child: Text(formatCents(line.lineTotalCents), textAlign: TextAlign.right, style: PosterText.bodyDefault),
          ),
        ],
      ),
    );
  }
}

class _CollectionPicker extends ConsumerWidget {
  const _CollectionPicker({required this.days});

  final List<OrderableDay> days;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (days.isEmpty) {
      return const Text('Nothing orderable right now.', style: PosterText.bodyDefault);
    }
    final selectedIso = ref.watch(selectedDayIsoProvider) ?? days.first.iso;
    final availabilityAsync = ref.watch(availabilityProvider(selectedIso));
    final basketSlotId = ref.watch(basketProvider).slotId;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final day in days)
              ChoiceChip(
                label: Text(day.dow),
                selected: day.iso == selectedIso,
                onSelected: (_) => ref.read(selectedDayIsoProvider.notifier).state = day.iso,
              ),
          ],
        ),
        const SizedBox(height: 12),
        availabilityAsync.when(
          data: (availability) => Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final slot in availability.slots)
                ChoiceChip(
                  label: Text(slot.label),
                  selected: slot.id == basketSlotId,
                  onSelected: slot.full ? null : (_) => ref.read(basketProvider.notifier).setCollection(selectedIso, slot.id),
                  disabledColor: PosterColors.border,
                  labelStyle: slot.full ? const TextStyle(decoration: TextDecoration.lineThrough) : null,
                ),
            ],
          ),
          loading: () => const CircularProgressIndicator(),
          error: (err, _) => Text('$err', style: PosterText.bodyDefault),
        ),
      ],
    );
  }
}

class _CheckoutFooter extends StatelessWidget {
  const _CheckoutFooter({required this.basket});

  final BasketState basket;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
        decoration: const BoxDecoration(
          color: PosterColors.white,
          border: Border(top: BorderSide(color: PosterColors.border)),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(formatCents(basket.totalCents), style: PosterText.priceCard.copyWith(color: PosterColors.navy)),
            ),
            ElevatedButton(
              onPressed: basket.hasCollectionChoice ? () => context.push('/checkout') : null,
              child: const Text('CHECKOUT'),
            ),
          ],
        ),
      ),
    );
  }
}
