import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/collection): replace with the real screen.
/// Backend: `GET /api/v1/staff/collection/?date=` (`staff/api_mobile_boards.py::collection_json`).
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class StaffCollectionScreen extends StatelessWidget {
  const StaffCollectionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Collection', body: Center(child: Text('TODO: Collection')));
  }
}
