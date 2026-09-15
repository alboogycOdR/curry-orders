import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../state/staff_auth.dart';
import '../../../theme/poster_tokens.dart';
import '../staff_scaffold.dart';

/// The 4th bottom-nav tab (docs/mobile/FLUTTER_APP_PLAN.md Phase 7's
/// staff-only IA rework) — everything that isn't frequent/urgent enough
/// to earn its own tab: Calendar, Payments, Cash, Daily controls, Menu
/// editor, New assisted order, Help, and the role-gated Settings/Team,
/// plus Sign out. Replaces Phase 6's hamburger `Drawer` (every screen
/// used to carry one) — one screen instead of chrome repeated on all
/// twelve. Also carries the staff-identity header the old drawer used
/// to show (avatar/name/role) since there's no separate Account tab
/// any more to put it on.
class MoreScreen extends ConsumerWidget {
  const MoreScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(staffAuthProvider).user;

    return StaffScaffold(
      title: 'More',
      automaticallyImplyLeading: false,
      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          Container(
            color: PosterColors.navy,
            padding: const EdgeInsets.all(PosterSpace.pageSidePadding),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor: PosterColors.bluePanel,
                  backgroundImage:
                      (user != null && user.avatarUrl.isNotEmpty) ? NetworkImage(user.avatarUrl) : null,
                  child: (user == null || user.avatarUrl.isEmpty)
                      ? Text(
                          user != null && user.name.isNotEmpty ? user.name[0].toUpperCase() : '?',
                          style: PosterText.cardTitle.copyWith(color: PosterColors.white),
                        )
                      : null,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user?.name ?? '',
                        style: PosterText.cardTitle.copyWith(fontSize: 18, color: PosterColors.white),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        user?.roleDisplay ?? '',
                        style: PosterText.bodyDefault.copyWith(color: PosterColors.mutedDark),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          const _SectionLabel('Daily operations'),
          const _MoreRow(label: 'Calendar', route: '/staff/calendar', icon: Icons.calendar_month_rounded),
          const _MoreRow(label: 'Payments', route: '/staff/payments', icon: Icons.account_balance_rounded),
          const _MoreRow(label: 'Cash', route: '/staff/cash', icon: Icons.payments_rounded),
          const _MoreRow(label: 'Daily controls', route: '/staff/daily-controls', icon: Icons.tune_rounded),
          const _MoreRow(label: 'Menu editor', route: '/staff/menu', icon: Icons.restaurant_menu_rounded),
          const Divider(height: 24, indent: 16, endIndent: 16),
          const _SectionLabel('Other'),
          const _MoreRow(
            label: 'New assisted order', route: '/staff/orders/new', icon: Icons.phone_forwarded_rounded,
          ),
          const _MoreRow(label: 'Help', route: '/staff/help', icon: Icons.help_outline_rounded),
          if (user?.isOwnerOrAdmin ?? false) ...[
            const Divider(height: 24, indent: 16, endIndent: 16),
            const _SectionLabel('Admin'),
            if (user!.isOwnerOrAdmin)
              const _MoreRow(label: 'Settings', route: '/staff/settings', icon: Icons.settings_rounded),
            if (user.isAdmin)
              const _MoreRow(label: 'Team', route: '/staff/team', icon: Icons.groups_rounded),
          ],
          const Divider(height: 24, indent: 16, endIndent: 16),
          ListTile(
            leading: const Icon(Icons.logout_rounded, color: PosterColors.error),
            title: const Text('Sign out', style: TextStyle(color: PosterColors.error)),
            onTap: () async {
              await ref.read(staffAuthProvider.notifier).logout();
              if (context.mounted) context.go('/staff/login');
            },
          ),
          const SizedBox(height: PosterSpace.bottomPagePadding),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.label);
  final String label;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
        child: Text(label, style: PosterText.eyebrow.copyWith(color: PosterColors.muted)),
      );
}

class _MoreRow extends StatelessWidget {
  const _MoreRow({required this.label, required this.route, required this.icon});

  final String label;
  final String route;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: PosterColors.navy),
      title: Text(label, style: PosterText.bodyLarge.copyWith(color: PosterColors.navy)),
      trailing: const Icon(Icons.chevron_right_rounded, color: PosterColors.muted),
      onTap: () => context.push(route),
    );
  }
}
