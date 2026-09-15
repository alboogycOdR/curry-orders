import 'package:flutter/material.dart';

import '../../theme/poster_tokens.dart';

/// Shared chrome for every staff screen — an app bar (title = section
/// name, optional trailing actions). Simplified 2026-09-15 when the
/// app became staff-only (`docs/mobile/FLUTTER_APP_PLAN.md` Phase 7):
/// navigation used to be a hamburger `Drawer` on every screen (Phase
/// 6); now that the whole app *is* the staff area, Inbox/Kitchen/
/// Collection are direct bottom-nav tabs (`app/staff_shell.dart`) and
/// everything else is one tap away via the More tab
/// (`features/staff/more/more_screen.dart`, which also carries the
/// staff-identity header the old drawer used to show) — so no screen
/// needs its own drawer any more.
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
    return Scaffold(
      backgroundColor: PosterColors.paper,
      appBar: AppBar(
        backgroundColor: PosterColors.navy,
        foregroundColor: PosterColors.white,
        automaticallyImplyLeading: automaticallyImplyLeading,
        title: Text(title.toUpperCase(), style: PosterText.button),
        actions: actions,
      ),
      body: SafeArea(child: body),
      floatingActionButton: floatingActionButton,
    );
  }
}
