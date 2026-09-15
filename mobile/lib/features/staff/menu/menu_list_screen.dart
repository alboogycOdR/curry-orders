import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/menu): replace with the real screen.
/// Backend: `GET /api/v1/staff/menu/` (`staff/api_mobile_menu.py::menu_list_json`).
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class StaffMenuListScreen extends StatelessWidget {
  const StaffMenuListScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Menu editor', body: Center(child: Text('TODO: Menu editor')));
  }
}
