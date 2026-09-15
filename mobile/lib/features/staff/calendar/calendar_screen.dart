import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/calendar): replace with the real screen.
/// Backend: `GET /api/v1/staff/calendar/` (`staff/api_mobile_payments.py::calendar_json`).
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class StaffCalendarScreen extends StatelessWidget {
  const StaffCalendarScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Calendar', body: Center(child: Text('TODO: Calendar')));
  }
}
