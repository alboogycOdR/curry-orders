import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/api_client.dart';

/// Shared HTTP infra (session cookie jar, CSRF interceptor) used by
/// both the staff API (`data/staff/staff_api.dart`) and, previously,
/// the customer-facing `RotiConnectApi` — that wrapper and every
/// provider that used to sit here (orderable days, featured dish,
/// availability, order detail) were removed 2026-09-15 when the app
/// became staff-only (`docs/mobile/FLUTTER_APP_PLAN.md` Phase 7). This
/// is now the only thing left in this file.
///
/// The default here (no `cookieStorageDir`) is an in-memory-only
/// fallback — `main.dart` always overrides this provider with a real
/// [ApiClient] built from a resolved `path_provider` directory before
/// `runApp()` (resolving that path is inherently async, and doing it
/// here would make every `ref.watch(apiClientProvider)` call async
/// too). A widget test that doesn't override this still gets a working
/// client, just without persistence across restarts — never a crash.
final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());
