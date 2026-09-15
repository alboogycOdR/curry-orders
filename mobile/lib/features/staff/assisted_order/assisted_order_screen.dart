import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/assisted-order): replace with the real screen.
/// Backend: `GET /api/v1/staff/orders/new/?date=` (form data) and
/// `POST /api/v1/staff/orders/new/` (create) —
/// `staff/api_mobile_assisted_order.py`.
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class AssistedOrderScreen extends StatelessWidget {
  const AssistedOrderScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(
      title: 'New assisted order',
      body: Center(child: Text('TODO: New assisted order')),
    );
  }
}
