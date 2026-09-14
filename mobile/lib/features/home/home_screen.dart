import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/models.dart';
import '../../state/api_providers.dart';
import '../../state/auth.dart';
import '../../theme/poster_tokens.dart';

/// Home — deliberately **not** a scroll-replica of the poster web
/// page's hero → collection → menu-teaser → promise-panel → steps →
/// final-CTA sequence (docs/mobile/FLUTTER_APP_PLAN.md Phase 3 IA note).
/// A returning app user wants two things fast: "what can I order right
/// now" and "where's my last order" — that's what this screen leads
/// with. The promise/steps/"how it works" content belongs to a one-time
/// first-run flow or a Help screen, not permanent Home real estate; it
/// isn't built yet (`docs/mobile/FLUTTER_APP_PLAN.md` doesn't list it
/// under Phase 3 for that reason).
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final daysAsync = ref.watch(orderableDaysProvider);
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
            if (!auth.restoring && auth.isSignedIn && auth.customer?.lastOrder != null)
              _LastOrderCard(orderNumber: auth.customer!.lastOrder!.orderNumber, publicToken: auth.customer!.lastOrder!.publicToken),
          ],
        ),
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
