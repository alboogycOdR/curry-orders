import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_client.dart';

/// Shared HTTP infra (session cookie jar, CSRF interceptor) used by
/// both the staff API (`data/staff/staff_api.dart`) and, previously,
/// the customer-facing `RotiConnectApi` — that wrapper and every
/// provider that used to sit here (orderable days, featured dish,
/// availability, order detail) were removed 2026-09-15 when the app
/// became staff-only (`docs/mobile/FLUTTER_APP_PLAN.md` Phase 7). This
/// is now the only thing left in this file.
final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());
