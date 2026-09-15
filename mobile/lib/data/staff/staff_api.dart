import 'package:dio/dio.dart';

import '../api_client.dart';
import '../api_exception.dart';
import 'staff_models.dart';

/// Shared response-parsing helper for every staff-mode screen's own dio
/// calls (`/api/v1/staff/...`, `src/staff/api_mobile*.py` on the
/// backend) — same `{error, message, fields}` shape as every response
/// this app parses, turned into an [ApiException] in one place. A free
/// function rather than a method on [StaffApi] itself, so each staff
/// screen's own repository/provider file (built independently —
/// docs/mobile/FLUTTER_APP_PLAN.md Phase 6) can call
/// `parseStaffJson(resp, ...)` without every screen editing one shared
/// class. (The app was customer+staff when this was written — the
/// customer-facing `RotiConnectApi`/`data/repository.dart` this used
/// to mirror was removed in Phase 7, when the app became staff-only.)
T parseStaffJson<T>(Response<dynamic> response, T Function(dynamic data) parse) {
  final status = response.statusCode ?? 0;
  if (status >= 200 && status < 300) {
    return parse(response.data);
  }
  final data = response.data;
  if (data is Map<String, dynamic>) {
    final rawFields = data['fields'];
    throw ApiException(
      code: (data['error'] as String?) ?? 'unknown',
      message: (data['message'] as String?) ?? 'Something went wrong.',
      statusCode: status,
      fields: rawFields is Map
          ? rawFields.map((key, value) => MapEntry(key.toString(), value.toString()))
          : null,
    );
  }
  throw ApiException(code: 'unknown', message: 'Something went wrong.', statusCode: status);
}

/// Staff auth only (`/api/v1/staff/auth/...`) — every other staff
/// endpoint (`/api/v1/staff/inbox/`, `.../kitchen/`, etc.) is called
/// directly from its own screen's provider file via the same
/// [ApiClient]'s `dio` (same cookie jar the customer side already
/// uses — a staff session and a customer session coexist in one Django
/// session, `staff.sessions` + `public.customer_sessions`), using
/// [parseStaffJson] above. Action endpoints (`transition`, `assign`,
/// `lock-kitchen`, `close-out`, `move-all`) live at `/manage/api/...`,
/// *not* under `/api/v1/staff/` — see `staff/urls_api_mobile.py`'s own
/// docstring for why they're reused as-is rather than re-exposed here.
class StaffApi {
  StaffApi(this._client);

  final ApiClient _client;

  /// `null` means "not staff" (200, not 401 — see `api_mobile.me_json`'s
  /// own docstring for why that's the expected common case, not an
  /// error).
  Future<StaffUser?> me() async {
    final resp = await _client.dio.get<dynamic>('staff/auth/me/');
    return parseStaffJson(resp, (d) {
      final user = (d as Map<String, dynamic>)['user'];
      return user == null ? null : StaffUser.fromJson(user as Map<String, dynamic>);
    });
  }

  Future<StaffUser> login({required String email, required String password}) async {
    final resp = await _client.dio.post<dynamic>(
      'staff/auth/login/',
      data: {'email': email, 'password': password},
    );
    return parseStaffJson(
      resp,
      (d) => StaffUser.fromJson((d as Map<String, dynamic>)['user'] as Map<String, dynamic>),
    );
  }

  Future<void> logout() async {
    final resp = await _client.dio.post<dynamic>('staff/auth/logout/');
    parseStaffJson(resp, (_) => null);
  }

  /// Native Google Sign-In (Phase 8) — `idToken` comes from
  /// `state/staff_auth.dart`'s Google sign-in flow (the `google_sign_in`
  /// package performs the OAuth dance on-device; this only ever sends
  /// the resulting ID token). Throws `ApiException(code: 'forbidden')`
  /// when the Google account isn't on the staff allowlist — same
  /// meaning as a wrong password on [login], just a different cause.
  Future<StaffUser> googleLogin({required String idToken}) async {
    final resp = await _client.dio.post<dynamic>(
      'staff/auth/google/',
      data: {'id_token': idToken},
    );
    return parseStaffJson(
      resp,
      (d) => StaffUser.fromJson((d as Map<String, dynamic>)['user'] as Map<String, dynamic>),
    );
  }
}
