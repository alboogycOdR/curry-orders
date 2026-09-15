import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/models.dart';
import '../../state/api_providers.dart';
import '../../state/auth.dart';
import '../../theme/poster_tokens.dart';
import '../../util/money.dart';

/// Home — deliberately **not** a scroll-replica of the poster web
/// page's hero → collection → menu-teaser → promise-panel → steps →
/// final-CTA sequence (docs/mobile/FLUTTER_APP_PLAN.md Phase 3 IA note).
/// A returning app user wants three things fast: "what can I order
/// right now" (the collection card, then the featured-dish card below
/// it), "what's this week's special" and "where's my last order" —
/// that's what this screen leads with. The promise/steps/"how it
/// works" content belongs to a one-time first-run flow or a Help
/// screen, not permanent Home real estate; it isn't built yet
/// (`docs/mobile/FLUTTER_APP_PLAN.md` doesn't list it under Phase 3
/// for that reason).
///
/// The featured-dish card (added 2026-09-15) is the one exception to
/// "not a scroll-replica" — unlike the promise panel/steps/final CTA
/// (marketing content, correctly left off), the hero dish is real,
/// sellable, staff-editable content (Menu editor's "Featured on
/// homepage" toggle) that answers Home's own stated question just as
/// directly as the collection card does. Found missing live: the app
/// had no endpoint at all for it until `GET /api/v1/featured/`.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final daysAsync = ref.watch(orderableDaysProvider);
    final featuredAsync = ref.watch(featuredDishProvider);
    final auth = ref.watch(authProvider);

    return ColoredBox(
      color: PosterColors.navy,
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
          children: [
            const Text(
              'Roti\nConnect',
              style: TextStyle(
                color: PosterColors.white,
                fontFamily: PosterText.fontFamily,
                fontSize: 48,
                fontWeight: FontWeight.w900,
                height: 0.85,
              ),
            ),
            const SizedBox(height: 24),
            daysAsync.when(
              data: (days) => _CollectionCard(days: days),
              loading: () => const _LoadingCard(),
              error: (err, _) => _ErrorCard(message: '$err'),
            ),
            const SizedBox(height: 16),
            featuredAsync.when(
              data: (dish) => dish == null ? const SizedBox.shrink() : _FeaturedCard(dish: dish),
              loading: () => const _LoadingCard(),
              // A missing featured dish shouldn't block the rest of
              // Home -- fail quiet, not with an error card, unlike the
              // collection card above (which the screen can't function
              // without).
              error: (err, _) => const SizedBox.shrink(),
            ),
            const SizedBox(height: 16),
            if (!auth.restoring && auth.isSignedIn && auth.customer?.lastOrder != null)
              _LastOrderCard(orderNumber: auth.customer!.lastOrder!.orderNumber, publicToken: auth.customer!.lastOrder!.publicToken),
          ],
        ),
      ),
    );
  }
}

class _FeaturedCard extends StatelessWidget {
  const _FeaturedCard({required this.dish});

  final FeaturedDish dish;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: PosterColors.white,
        borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
        boxShadow: PosterShadows.gold(),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (dish.photoUrl.isNotEmpty)
            AspectRatio(
              aspectRatio: 16 / 9,
              child: Image.network(
                dish.photoUrl,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stack) =>
                    const ColoredBox(color: PosterColors.bluePanel),
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text("THIS WEEK'S SPECIAL", style: PosterText.eyebrow.copyWith(color: PosterColors.blue)),
                const SizedBox(height: 6),
                Text(
                  dish.name.toUpperCase(),
                  style: PosterText.cardTitle.copyWith(color: PosterColors.navy),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                if (dish.shortDescription.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    dish.shortDescription,
                    style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(formatCents(dish.priceCents), style: PosterText.priceCard.copyWith(color: PosterColors.navy)),
                    ElevatedButton(
                      onPressed: () => context.go('/menu'),
                      child: const Text('ORDER THE SPECIAL'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CollectionCard extends StatelessWidget {
  const _CollectionCard({required this.days});

  final List<OrderableDay> days;

  @override
  Widget build(BuildContext context) {
    if (days.isEmpty) {
      return const _ErrorCard(message: 'Nothing orderable right now — check back soon.');
    }
    final soonest = days.first;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: PosterColors.bluePanel,
        border: Border.all(color: PosterColors.blue, width: 2),
        borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
        boxShadow: PosterShadows.gold(),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('COLLECTION', style: PosterText.eyebrow.copyWith(color: PosterColors.gold)),
          const SizedBox(height: 8),
          Text(
            'Ordering for ${soonest.long}',
            style: PosterText.cardTitle.copyWith(color: PosterColors.white),
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () => context.go('/menu'),
            child: const Text('SEE THE MENU'),
          ),
        ],
      ),
    );
  }
}

class _LastOrderCard extends StatelessWidget {
  const _LastOrderCard({required this.orderNumber, required this.publicToken});

  final String orderNumber;
  final String publicToken;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => context.push('/orders/$publicToken'),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: PosterColors.white,
          borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
        ),
        child: Row(
          children: [
            const Icon(Icons.receipt_long_rounded, color: PosterColors.navy),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Your last order', style: PosterText.metadata),
                  Text(orderNumber, style: PosterText.cardTitle.copyWith(fontSize: 18)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right_rounded, color: PosterColors.muted),
          ],
        ),
      ),
    );
  }
}

class _LoadingCard extends StatelessWidget {
  const _LoadingCard();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(vertical: 32),
        child: Center(child: CircularProgressIndicator(color: PosterColors.gold)),
      );
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: PosterColors.white,
          borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
        ),
        child: Text(message, style: PosterText.bodyDefault),
      );
}
