import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state/notifications.dart';
import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

/// Notifications on/off (docs/mobile/FLUTTER_APP_PLAN.md Phase 8) —
/// reached from the More tab, not nested inside the owner/admin-only
/// Settings screen; see `state/notifications.dart`'s own docstring for
/// why. One toggle for now ("order activity alerts" — new orders,
/// kitchen-ready, collected/picked-up, and other order-trigger events);
/// per-event toggles are a reasonable follow-up once there's real
/// signal on which alerts staff actually want granular control over,
/// not built speculatively here.
class NotificationsScreen extends ConsumerWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final enabled = ref.watch(notificationsEnabledProvider);

    return StaffScaffold(
      title: 'Notifications',
      body: ListView(
        padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: PosterColors.white,
              borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
              border: Border.all(color: PosterColors.border),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: const BoxDecoration(
                    color: PosterColors.bluePanel, shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.notifications_active_rounded, color: PosterColors.gold),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Order activity alerts', style: PosterText.cardTitle.copyWith(fontSize: 16, color: PosterColors.navy)),
                      const SizedBox(height: 2),
                      Text(
                        'New orders, kitchen-ready, and collections',
                        style: PosterText.bodyDefault.copyWith(color: PosterColors.muted),
                      ),
                    ],
                  ),
                ),
                Switch(
                  value: enabled,
                  activeThumbColor: PosterColors.blue,
                  onChanged: (value) => ref.read(notificationsEnabledProvider.notifier).setEnabled(value),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _InfoCallout(
            icon: Icons.bolt_rounded,
            text: 'When this is on, you\'ll get an alert the moment a new order comes in, '
                'a kitchen ticket is marked ready, or an order is collected — '
                'so you don\'t have to keep the app open and watch a board.',
          ),
          const SizedBox(height: 12),
          _InfoCallout(
            icon: Icons.info_outline_rounded,
            color: PosterColors.mutedDark,
            text: 'This is a per-device setting — turning it off here only stops alerts on '
                'this phone, not for the rest of the team.',
          ),
        ],
      ),
    );
  }
}

class _InfoCallout extends StatelessWidget {
  const _InfoCallout({required this.icon, required this.text, this.color = PosterColors.blue});

  final IconData icon;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(PosterSpace.radiusButton),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: PosterText.bodyDefault.copyWith(color: PosterColors.navy))),
        ],
      ),
    );
  }
}
