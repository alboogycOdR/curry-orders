import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/staff_auth.dart';
import '../theme/poster_tokens.dart';

/// App shell for the (now staff-only) app: a 4-tab bottom nav — Inbox,
/// Kitchen, Collection, More — wrapping a `StatefulShellRoute`
/// (`app/router.dart`). Also doubles as the app's auth gate
/// (docs/mobile/FLUTTER_APP_PLAN.md Phase 7): since every screen in
/// this app is now a staff screen, there's no separate "Account tab"
/// to hold a login link any more — this shell itself checks
/// [staffAuthProvider] on every build and bounces to `/staff/login`
/// the moment it's anything but signed-in (covers both the cold-start
/// "not signed in yet" case and a session expiring mid-use — the
/// staff session's own 12h absolute / 2h idle lifetime,
/// `staff.sessions`).
class StaffShell extends ConsumerWidget {
  const StaffShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(staffAuthProvider);

    if (auth.restoring) {
      return const _Splash();
    }
    if (!auth.isStaff) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (context.mounted) context.go('/staff/login');
      });
      return const _Splash();
    }

    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: _StaffBottomNav(navigationShell: navigationShell),
    );
  }
}

class _Splash extends StatelessWidget {
  const _Splash();

  @override
  Widget build(BuildContext context) => const ColoredBox(
        color: PosterColors.navy,
        child: Center(child: CircularProgressIndicator(color: PosterColors.gold)),
      );
}

class _StaffBottomNav extends StatelessWidget {
  const _StaffBottomNav({required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: PosterColors.navy,
        border: Border(top: BorderSide(color: PosterColors.blue, width: 2)),
      ),
      child: SafeArea(
        child: SizedBox(
          height: PosterSpace.bottomNavHeight,
          child: Row(
            children: [
              _NavItem(
                icon: Icons.inbox_rounded, label: 'Inbox',
                selected: navigationShell.currentIndex == 0,
                onTap: () => navigationShell.goBranch(0),
              ),
              _NavItem(
                icon: Icons.soup_kitchen_rounded, label: 'Kitchen',
                selected: navigationShell.currentIndex == 1,
                onTap: () => navigationShell.goBranch(1),
              ),
              _NavItem(
                icon: Icons.storefront_rounded, label: 'Collection',
                selected: navigationShell.currentIndex == 2,
                onTap: () => navigationShell.goBranch(2),
              ),
              _NavItem(
                icon: Icons.more_horiz_rounded, label: 'More',
                selected: navigationShell.currentIndex == 3,
                onTap: () => navigationShell.goBranch(3),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? PosterColors.gold : PosterColors.mutedDark;
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 2),
            Text(label, style: PosterText.metadata.copyWith(color: color)),
          ],
        ),
      ),
    );
  }
}
