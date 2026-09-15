import 'package:go_router/go_router.dart';

import '../features/staff/assisted_order/assisted_order_screen.dart';
import '../features/staff/calendar/calendar_screen.dart';
import '../features/staff/cash/cash_screen.dart';
import '../features/staff/collection/collection_screen.dart';
import '../features/staff/daily_controls/daily_controls_screen.dart';
import '../features/staff/help/staff_help_screen.dart';
import '../features/staff/inbox/inbox_screen.dart';
import '../features/staff/kitchen/kitchen_screen.dart';
import '../features/staff/menu/dish_form_screen.dart';
import '../features/staff/menu/menu_list_screen.dart';
import '../features/staff/more/more_screen.dart';
import '../features/staff/payments/payments_screen.dart';
import '../features/staff/settings/staff_settings_screen.dart';
import '../features/staff/staff_login_screen.dart';
import '../features/staff/team/team_screen.dart';
import 'staff_shell.dart';

/// The whole app is staff-only (docs/mobile/FLUTTER_APP_PLAN.md Phase
/// 7 — every customer-facing screen was removed 2026-09-15). One
/// `StatefulShellRoute` (Inbox / Kitchen / Collection / More — the
/// three highest-frequency, during-service boards get a direct tab;
/// everything else is one tap away via More) plus the remaining eight
/// screens as full-screen pushes *outside* the shell, reached only via
/// the More tab's own list. `StaffShell` (the shell's `builder`) is
/// also this app's auth gate — see its own docstring.
final appRouter = GoRouter(
  initialLocation: '/staff/inbox',
  routes: [
    GoRoute(path: '/staff/login', builder: (context, state) => const StaffLoginScreen()),
    StatefulShellRoute.indexedStack(
      builder: (context, state, navigationShell) => StaffShell(navigationShell: navigationShell),
      branches: [
        StatefulShellBranch(
          routes: [GoRoute(path: '/staff/inbox', builder: (context, state) => const InboxScreen())],
        ),
        StatefulShellBranch(
          routes: [GoRoute(path: '/staff/kitchen', builder: (context, state) => const KitchenScreen())],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/staff/collection',
              builder: (context, state) => const StaffCollectionScreen(),
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [GoRoute(path: '/staff/more', builder: (context, state) => const MoreScreen())],
        ),
      ],
    ),
    GoRoute(path: '/staff/calendar', builder: (context, state) => const StaffCalendarScreen()),
    GoRoute(path: '/staff/payments', builder: (context, state) => const PaymentsScreen()),
    GoRoute(path: '/staff/cash', builder: (context, state) => const CashScreen()),
    GoRoute(path: '/staff/daily-controls', builder: (context, state) => const DailyControlsScreen()),
    GoRoute(path: '/staff/menu', builder: (context, state) => const StaffMenuListScreen()),
    GoRoute(path: '/staff/menu/new', builder: (context, state) => const DishFormScreen()),
    GoRoute(
      path: '/staff/menu/:id',
      builder: (context, state) => DishFormScreen(dishId: int.parse(state.pathParameters['id']!)),
    ),
    GoRoute(path: '/staff/orders/new', builder: (context, state) => const AssistedOrderScreen()),
    GoRoute(path: '/staff/help', builder: (context, state) => const StaffHelpScreen()),
    GoRoute(path: '/staff/settings', builder: (context, state) => const StaffSettingsScreen()),
    GoRoute(path: '/staff/team', builder: (context, state) => const TeamScreen()),
  ],
);
