import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../state/staff_auth.dart';
import '../../theme/poster_tokens.dart';

/// Shared chrome for every staff screen (docs/mobile/FLUTTER_APP_PLAN.md
/// Phase 6): an app bar (hamburger opens the drawer, title = section
/// name) plus a `Drawer` listing all twelve areas, grouped and ordered
/// exactly like the web staff nav's own dropdown (`base.html`'s staff
/// menu) so the *inventory* is familiar even though each screen's own
/// layout is redesigned for a phone, not a literal port (the IA
/// decision this phase was built under — see FLUTTER_APP_PLAN.md's own
/// "Staff IA approach" note).
///
/// Deliberately a plain widget each screen wraps its own body in
/// (`StaffScaffold(title: ..., body: ...)`), not a go_router
/// `ShellRoute` — every staff screen was built independently in
/// parallel; a plain wrapper needs no shared routing state and can't
/// merge-conflict the way a shared shell/router file would.
class StaffScaffold extends ConsumerWidget {
  const StaffScaffold({
    super.key,
    required this.title,
    required this.body,
    this.actions,
    this.floatingActionButton,
  });

  final String title;
  final Widget body;
  final List<Widget>? actions;
  final Widget? floatingActionButton;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      backgroundColor: PosterColors.paper,
      appBar: AppBar(
        backgroundColor: PosterColors.navy,
        foregroundColor: PosterColors.white,
        title: Text(title.toUpperCase(), style: PosterText.button),
        actions: actions,
      ),
      drawer: const _StaffDrawer(),
      body: SafeArea(child: body),
      floatingActionButton: floatingActionButton,
    );
  }
}

class _StaffNavItem {
  const _StaffNavItem(this.label, this.route, this.icon);
  final String label;
  final String route;
  final IconData icon;
}

const _dailyOpsItems = [
  _StaffNavItem('Inbox', '/staff/inbox', Icons.inbox_rounded),
  _StaffNavItem('Calendar', '/staff/calendar', Icons.calendar_month_rounded),
  _StaffNavItem('Kitchen desk', '/staff/kitchen', Icons.soup_kitchen_rounded),
  _StaffNavItem('Collection', '/staff/collection', Icons.storefront_rounded),
  _StaffNavItem('Payments', '/staff/payments', Icons.account_balance_rounded),
  _StaffNavItem('Cash', '/staff/cash', Icons.payments_rounded),
  _StaffNavItem('Daily controls', '/staff/daily-controls', Icons.tune_rounded),
  _StaffNavItem('Menu editor', '/staff/menu', Icons.restaurant_menu_rounded),
];

const _otherItems = [
  _StaffNavItem('New assisted order', '/staff/orders/new', Icons.phone_forwarded_rounded),
  _StaffNavItem('Help', '/staff/help', Icons.help_outline_rounded),
];

class _StaffDrawer extends ConsumerWidget {
  const _StaffDrawer();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(staffAuthProvider);
    final user = auth.user;
    final path = GoRouterState.of(context).uri.path;

    return Drawer(
      backgroundColor: PosterColors.white,
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          Container(
            color: PosterColors.navy,
            padding: const EdgeInsets.fromLTRB(
              PosterSpace.pageSidePadding, 48, PosterSpace.pageSidePadding, 20,
            ),
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
          for (final item in _dailyOpsItems) _DrawerRow(item: item, selected: path == item.route),
          const Divider(height: 24, indent: 16, endIndent: 16),
          for (final item in _otherItems) _DrawerRow(item: item, selected: path == item.route),
          if (user?.isOwnerOrAdmin ?? false)
            _DrawerRow(
              item: const _StaffNavItem('Settings', '/staff/settings', Icons.settings_rounded),
              selected: path == '/staff/settings',
            ),
          if (user?.isAdmin ?? false)
            _DrawerRow(
              item: const _StaffNavItem('Team', '/staff/team', Icons.groups_rounded),
              selected: path == '/staff/team',
            ),
          const Divider(height: 24, indent: 16, endIndent: 16),
          ListTile(
            leading: const Icon(Icons.logout_rounded, color: PosterColors.error),
            title: const Text('Sign out', style: TextStyle(color: PosterColors.error)),
            onTap: () async {
              Navigator.of(context).pop();
              await ref.read(staffAuthProvider.notifier).logout();
              if (context.mounted) context.go('/account');
            },
          ),
        ],
      ),
    );
  }
}

class _DrawerRow extends StatelessWidget {
  const _DrawerRow({required this.item, required this.selected});

  final _StaffNavItem item;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      selected: selected,
      selectedTileColor: PosterColors.bluePanel.withValues(alpha: 0.08),
      leading: Icon(item.icon, color: selected ? PosterColors.blue : PosterColors.navy),
      title: Text(
        item.label,
        style: PosterText.bodyLarge.copyWith(
          color: PosterColors.navy,
          fontWeight: selected ? FontWeight.w800 : FontWeight.w500,
        ),
      ),
      onTap: () {
        Navigator.of(context).pop();
        if (!selected) context.go(item.route);
      },
    );
  }
}
