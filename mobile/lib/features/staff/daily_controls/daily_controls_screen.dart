import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/daily-controls): replace with the real screen.
/// Backend: `GET/POST /api/v1/staff/days/<date>/` (`staff/api_mobile_daily_controls.py::daily_controls_json`).
/// "Move all" reuses the existing `POST /manage/api/days/<date>/slots/<slot_id>/move-all`.
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class DailyControlsScreen extends StatelessWidget {
  const DailyControlsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Daily controls', body: Center(child: Text('TODO: Daily controls')));
  }
}
