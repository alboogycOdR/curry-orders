import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/inbox): replace with the real screen.
/// Backend: `GET /api/v1/staff/inbox/` (`staff/api_mobile_boards.py::inbox_json`).
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class InboxScreen extends StatelessWidget {
  const InboxScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Inbox', body: Center(child: Text('TODO: Inbox')));
  }
}
