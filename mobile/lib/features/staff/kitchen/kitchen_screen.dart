import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/kitchen): replace with the real screen.
/// Backend: `GET /api/v1/staff/kitchen/?date=` (`staff/api_mobile_boards.py::kitchen_json`).
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class KitchenScreen extends StatelessWidget {
  const KitchenScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Kitchen desk', body: Center(child: Text('TODO: Kitchen desk')));
  }
}
