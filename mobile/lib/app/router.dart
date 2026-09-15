import 'package:go_router/go_router.dart';

import '../features/account/account_screen.dart';
import '../features/basket/basket_screen.dart';
import '../features/checkout/checkout_screen.dart';
import '../features/home/home_screen.dart';
import '../features/menu/menu_screen.dart';
import '../features/orders/order_detail_screen.dart';
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
import '../features/staff/payments/payments_screen.dart';
import '../features/staff/settings/staff_settings_screen.dart';
import '../features/staff/staff_login_screen.dart';
import '../features/staff/team/team_screen.dart';
import 'shell.dart';

/// One `StatefulShellRoute` branch per bottom-nav tab: Home, Menu,
/// Basket, **Account** — not "Orders" (docs/mobile/FLUTTER_APP_PLAN.md
/// Phase 3 IA decision: Account gets a real persistent home instead of
/// the poster web build's "no tab of its own", since order history
/// lives there too). Checkout and order detail are full-screen pushes
/// *outside* the shell (their own back stack, no bottom nav) — reached
/// from Basket and Account respectively.
final appRouter = GoRouter(
  initialLocation: '/home',
  routes: [
    StatefulShellRoute.indexedStack(
      builder: (context, state, navigationShell) => AppShell(navigationShell: navigationShell),
      branches: [
        StatefulShellBranch(
          routes: [GoRoute(path: '/home', builder: (context, state) => const HomeScreen())],
        ),
        StatefulShellBranch(
          routes: [GoRoute(path: '/menu', builder: (context, state) => const MenuScreen())],
        ),
        StatefulShellBranch(
          routes: [GoRoute(path: '/basket', builder: (context, state) => const BasketScreen())],
        ),
        StatefulShellBranch(
          routes: [GoRoute(path: '/account', builder: (context, state) => const AccountScreen())],
        ),
      ],
    ),
    GoRoute(path: '/checkout', builder: (context, state) => const CheckoutScreen()),
    GoRoute(
      path: '/orders/:token',
      builder: (context, state) => OrderDetailScreen(publicToken: state.pathParameters['token']!),
    ),
    // Staff mode (docs/mobile/FLUTTER_APP_PLAN.md Phase 6) — its own
    // full-screen stack, outside the customer bottom-nav shell
    // entirely (reached from Account's "Staff dashboard" card, not a
    // tab of its own; see `features/staff/staff_scaffold.dart`'s own
    // docstring for why each screen carries its own chrome/drawer
    // rather than a shared `ShellRoute`).
    GoRoute(path: '/staff/login', builder: (context, state) => const StaffLoginScreen()),
    GoRoute(path: '/staff/inbox', builder: (context, state) => const InboxScreen()),
    GoRoute(path: '/staff/calendar', builder: (context, state) => const StaffCalendarScreen()),
    GoRoute(path: '/staff/kitchen', builder: (context, state) => const KitchenScreen()),
    GoRoute(path: '/staff/collection', builder: (context, state) => const StaffCollectionScreen()),
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
