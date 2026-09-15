import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/help): replace with the real screen.
/// No backend JSON needed — the guide already exists as a live web page
/// (`/manage/help/`, `docs/STAFF_GUIDE.md`) with stable per-section
/// anchor ids. Build this as a native list of section links (label +
/// anchor, hardcoded from that page's own table of contents) that open
/// `https://roticonnect.duckdns.org/manage/help/#<anchor>` via
/// `url_launcher` (add the package) — avoids re-porting/duplicating 600+
/// lines of guide content that would drift out of sync with the source.
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full spec.
class StaffHelpScreen extends StatelessWidget {
  const StaffHelpScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Help', body: Center(child: Text('TODO: Help')));
  }
}
