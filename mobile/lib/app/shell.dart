import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/basket.dart';
import '../theme/poster_tokens.dart';

/// The 4-tab bottom nav shell: Home, Menu, Basket, **Account**. Visual
/// chrome (fixed, 72px, black, 2px blue top rule; active tab gold with a
/// 3px gold bar; basket gold count badge; 44px min targets) follows the
/// poster style guide §10.4/§8.3, but the fourth tab is a deliberate
/// departure from it — the guide's own tab is "Orders", with Account
/// unresolved (open question 6). docs/mobile/FLUTTER_APP_PLAN.md Phase 3
/// settles that for the app: Account is a real persistent tab (profile +
/// sign-in/up + order history + guest lookup all live there), not an
/// omission — a native app's whole value is the repeat, identified
/// customer, and push notifications (Phase 4) require one anyway.
///
/// Wraps go_router's [StatefulNavigationShell] so each tab keeps its own
/// navigation stack (§10.4 doesn't call for state loss switching tabs).
class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final basketCount = ref.watch(basketProvider).itemCount;
    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: DecoratedBox(
        decoration: const BoxDecoration(
          color: PosterColors.black,
          border: Border(top: BorderSide(color: PosterColors.blue, width: 2)),
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: PosterSpace.bottomNavHeight,
            child: Row(
              children: [
                _NavItem(
                  label: 'Home',
                  icon: Icons.home_rounded,
                  selected: navigationShell.currentIndex == 0,
                  onTap: () => _goBranch(0),
                ),
                _NavItem(
                  label: 'Menu',
                  icon: Icons.restaurant_menu_rounded,
                  selected: navigationShell.currentIndex == 1,
                  onTap: () => _goBranch(1),
                ),
                _NavItem(
                  label: 'Basket',
                  icon: Icons.shopping_bag_rounded,
                  selected: navigationShell.currentIndex == 2,
                  onTap: () => _goBranch(2),
                  badgeCount: basketCount,
                ),
                _NavItem(
                  label: 'Account',
                  icon: Icons.person_rounded,
                  selected: navigationShell.currentIndex == 3,
                  onTap: () => _goBranch(3),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _goBranch(int index) {
    navigationShell.goBranch(
      index,
      // Tapping the already-active tab returns it to its root, matching
      // standard bottom-nav behaviour (and the poster reference's own
      // single-page-per-tab model — no accumulating back stack per tab).
      initialLocation: index == navigationShell.currentIndex,
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
    this.badgeCount = 0,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;
  final int badgeCount;

  @override
  Widget build(BuildContext context) {
    final color = selected ? PosterColors.gold : PosterColors.mutedDark;

    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (selected)
              Container(height: 3, color: PosterColors.gold)
            else
              const SizedBox(height: 3),
            const SizedBox(height: 8),
            Stack(
              clipBehavior: Clip.none,
              children: [
                Icon(icon, color: color, size: 24),
                if (badgeCount > 0)
                  Positioned(
                    right: -8,
                    top: -6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                      decoration: const BoxDecoration(
                        color: PosterColors.gold,
                        shape: BoxShape.circle,
                      ),
                      constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
                      child: Text(
                        '$badgeCount',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w900,
                          color: PosterColors.navy,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: color),
            ),
          ],
        ),
      ),
    );
  }
}
