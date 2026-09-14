import 'package:go_router/go_router.dart';

import '../features/account/account_screen.dart';
import '../features/basket/basket_screen.dart';
import '../features/checkout/checkout_screen.dart';
import '../features/home/home_screen.dart';
import '../features/menu/menu_screen.dart';
import '../features/orders/order_detail_screen.dart';
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
  ],
);
