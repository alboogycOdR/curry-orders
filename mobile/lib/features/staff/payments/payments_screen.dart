import 'package:flutter/material.dart';

import '../staff_scaffold.dart';

/// TODO(staff-phase6/payments): replace with the real screen.
/// Backend: `GET /api/v1/staff/payments/` (`staff/api_mobile_payments.py::payments_json`).
/// See docs/mobile/FLUTTER_APP_PLAN.md Phase 6 for the full functional spec.
class PaymentsScreen extends StatelessWidget {
  const PaymentsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const StaffScaffold(title: 'Payments', body: Center(child: Text('TODO: Payments')));
  }
}
