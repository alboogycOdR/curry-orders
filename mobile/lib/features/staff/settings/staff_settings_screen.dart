import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/settings): replace with the real screen.
/// Owner/Admin only — `staffAuthProvider`'s `user.isOwnerOrAdmin` gate
/// already keeps this out of the drawer for a Manager; the screen
/// itself should also refuse gracefully (403 from the backend) rather
/// than assume the drawer is the only way in.
/// Backend: `GET/POST /api/v1/staff/settings/` (`staff/api_mobile_admin.py::settings_json`).
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class StaffSettingsScreen extends StatelessWidget {
  const StaffSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Settings', body: Center(child: Text('TODO: Settings')));
  }
}
