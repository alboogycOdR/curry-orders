import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/team): replace with the real screen.
/// Admin only — see `staff_settings_screen.dart`'s own note on the same
/// gating pattern.
/// Backend: `GET /api/v1/staff/team/` + `POST` invite/change-role/remove
/// (`staff/api_mobile_admin.py::team_json`/`team_member_json`).
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class TeamScreen extends StatelessWidget {
  const TeamScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Team', body: Center(child: Text('TODO: Team')));
  }
}
