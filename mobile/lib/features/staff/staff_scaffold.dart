import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/router.dart';
import '../../theme/poster_tokens.dart';

/// Shared chrome for every staff screen — an app bar (small branding
/// mark + title = section name, optional trailing actions). Simplified
/// 2026-09-15 when the app became staff-only
/// (`docs/mobile/FLUTTER_APP_PLAN.md` Phase 7): navigation used to be a
/// hamburger `Drawer` on every screen (Phase 6); now that the whole app
/// *is* the staff area, Inbox/Kitchen/Collection/Calendar/Payments are
/// direct bottom-nav tabs (`app/staff_shell.dart`) and everything else
/// is one tap away via the More tab (`features/staff/more/
/// more_screen.dart`, which also carries the staff-identity header the
/// old drawer used to show) — so no screen needs its own drawer any
/// more.
///
/// The small owner-portrait mark next to the title (added same day,
/// explicit direction: "bring through the branding... if we can reduce
/// it in size so that it does not stand out too much") is the same
/// image the web/poster header uses, re-exported small for the app
/// bundle — see `assets/img/owner-avatar.jpg`'s own comment in
/// `pubspec.yaml` for why it isn't the full-size web asset.
///
/// Also where the "back always goes to Inbox" behaviour actually lives
/// (Phase 9) — **not** `main.dart`'s `MaterialApp.router.builder` as
/// first built: a `PopScope` positioned there sits *above* go_router's
/// own `Navigator`/`Router` widgets entirely, so it's never registered
/// with the pop-propagation chain the system back button actually
/// walks — it silently intercepted nothing, and every screen just fell
/// through to the OS default (pop if possible, else exit). Found live:
/// the back button exited the app from the Calendar tab instead of
/// going to Inbox. Every staff screen wraps its content in this class,
/// so a `PopScope` *here* — genuinely inside each route's own widget
/// subtree — is what actually gets consulted, for shell tabs and
/// pushed screens (Cash, Menu editor, Team, ...) alike.
class StaffScaffold extends StatelessWidget {
  const StaffScaffold({
    super.key,
    required this.title,
    required this.body,
    this.actions,
    this.floatingActionButton,
    this.automaticallyImplyLeading = true,
  });

  final String title;
  final Widget body;
  final List<Widget>? actions;
  final Widget? floatingActionButton;

  /// `false` for a screen reached only from the More tab's own list
  /// (nothing to do — go_router already gives it a back arrow) is the
  /// default `true` case; kept as a parameter rather than hardcoded in
  /// case a future bottom-nav-tab screen (no back stack of its own)
  /// needs to suppress it.
  final bool automaticallyImplyLeading;

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        final location = appRouter.routerDelegate.currentConfiguration.uri.toString();
        if (location == '/staff/inbox') {
          SystemNavigator.pop();
        } else {
          appRouter.go('/staff/inbox');
        }
      },
      child: Scaffold(
        backgroundColor: PosterColors.paper,
        appBar: AppBar(
          backgroundColor: PosterColors.navy,
          foregroundColor: PosterColors.white,
          automaticallyImplyLeading: automaticallyImplyLeading,
          title: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircleAvatar(
                radius: 12,
                backgroundImage: AssetImage('assets/img/owner-avatar.jpg'),
              ),
              const SizedBox(width: 10),
              Text(title.toUpperCase(), style: PosterText.button),
            ],
          ),
          actions: actions,
        ),
        body: SafeArea(child: body),
        floatingActionButton: floatingActionButton,
      ),
    );
  }
}
