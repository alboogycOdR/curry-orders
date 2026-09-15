import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/cash): replace with the real screen.
/// Backend: `GET /api/v1/staff/cash/` (`staff/api_mobile_boards.py::cash_json`).
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class CashScreen extends StatelessWidget {
  const CashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Cash', body: Center(child: Text('TODO: Cash')));
  }
}
